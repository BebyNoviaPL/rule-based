from flask import Flask, render_template, request, redirect, url_for, flash, send_file, send_from_directory, safe_join, abort, jsonify
from werkzeug.utils import secure_filename
from flask_mysqldb import MySQL
import xlrd, xlwt
import os, pandas as pd, numpy as np, itertools, sys
from operator import itemgetter
from Sastrawi.Stemmer.StemmerFactory import StemmerFactory
import csv, string

UPLOAD_FOLDER = "uploads/"
ALLOWED_EXTENSIONS = {'xls', 'xlsx'}

app = Flask(__name__)
# UPLOAD_FOLDER = os.path.join(app.root_path, "/uploads") 
app.secret_key = 'many random bytes'
app.config['MYSQL_HOST'] = 'localhost'
app.config['MYSQL_USER'] = 'root'
app.config['MYSQL_PASSWORD'] = ''
app.config['MYSQL_DB'] = 'sentimen_analisis'
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

filename = 'tagging_kamus.xlsx'
pattern = ["Preposisi", "Verba", "Adjektiva", "Nomina", "Adverbia"]

adj_df = pd.read_excel(filename, 'Adjektiva')
verba_df = pd.read_excel(filename, 'Verba')
adverbia_df = pd.read_excel(filename, 'Adverbia')
preposisi_df = pd.read_excel(filename, 'Preposisi')
nomina_df = pd.read_excel(filename, 'Nomina')

frames = [adj_df, verba_df, adverbia_df, preposisi_df, nomina_df]
posdf = pd.concat(frames)
factory = StemmerFactory()
stemmer = factory.create_stemmer()
df_stopwords = pd.read_excel('stopwords.xlsx')
df_stopwords = df_stopwords['kata'].values.tolist()

mysql = MySQL(app)

@app.route('/')
def Index():
    
    return render_template('index.html')

@app.route('/ruleLama', methods = ['POST'])
def ruleLama():

    if request.method == "POST":
        flash("Data Inserted Successfully")
        rule_lama = getSentiment(tweet, 5)
        cur = mysql.connection.cursor()
        cur.execute("INSERT INTO training (rule_lama) VALUES (%s)", (rule_lama))
        mysql.connection.commit()
        cur.close()
        return redirect(url_for('Index'))
 
def convertSentence(sentence):
    """
    Return Part Of Speech of every word in sentence
    """
    pos = []
    for word in sentence.split(" "):
        try:
            pos.append(posdf.loc[posdf["word"] == word, 'pos'].iloc[0])
        except:
            pos.append("Unknown")
            continue
    return pos

def sentimentNANDOperator(a, b):
    # Measure two value with NAND Operator
    if a == 0 or b == 0: return (a+b)
    return 1 if a+b > 0 else -1

def sentimentANDOperator(a, b):
    # Measure two value with AND Operator
    if a == 0 or b == 0: return (a+b)
    return 1 if a == b else -1

def singleRule(data):
    # Return sentiment degree of a word
    return posdf.loc[posdf["word"] == data, 'sentiment'].iloc[0]

def verbAdjectiveRule(idx, words, pos):
    try:
        # Find next pattern index
        idxAdj = pos[idx+1:].index("Adjektiva")+(idx+1)
        if idxAdj >= idx+1:
            adjsenti = posdf.loc[posdf["word"] == words[idxAdj], 'sentiment'].iloc[0]
            return idxAdj, adjsenti
        return False
    except ValueError:
        return False

def verbRule(idx, words, pos):
    """
        Verb rule method will return only verb sentiment degree,
        If verb not following by adjective part of speech.
        If there's adjective after verb then method will call verbAdjectiveRule
        to get adjective sentiment degree.
    """
    verbsenti = posdf.loc[posdf["word"] == words[idx], 'sentiment'].iloc[0]
    try:
        isverbplusadjective, adjsenti = verbAdjectiveRule(idx, words, pos)
        return isverbplusadjective, sentimentNANDOperator(verbsenti, adjsenti)
    except TypeError:
        return idx, verbsenti

def prepositionAdjectiveRule(idx, preposenti, datalist):
      # Measure Prepo + Adjective sentiment degree
    adjsenti = posdf.loc[posdf["word"] == datalist['words'][idx+1], 'sentiment'].iloc[0]
    return sentimentANDOperator(preposenti,adjsenti)

def prepositionVerbRule(idx, preposenti, datalist):
      # Measure Prepo + Verb sentiment degree
    isanyadjidx, verbsenti = verbRule(idx+1,datalist['words'], datalist['pos'])
    if isanyadjidx: # Check if there's any adjective after verb
        return isanyadjidx, sentimentANDOperator(preposenti,verbsenti)
    return idx, sentimentNANDOperator(preposenti,verbsenti)

def prepositionRule(idx, words, pos):
    """
        Preposition rule method will not return prepoition sentiment degree,
        If preposition not following by adjective or verb part of speech.
        If there's adjective or verb after preposition then method will call
        prepositionAdjectiveRule or prepositionVerbRule to get rule combination sentiment degree.
    """
    datalist = {'words': words, 'pos': pos}
    preposenti =  posdf.loc[posdf["word"] == words[idx], 'sentiment'].iloc[0]
    try:
        if pos[idx+1] == "Adjektiva":
            return [idx+1], prepositionAdjectiveRule(idx, preposenti, datalist)
        elif pos[idx+1] == "Verba":
            idxAdj, sentiment = prepositionVerbRule(idx, preposenti, datalist)
            return [idx+1, idxAdj], sentiment 
        return idx, 0
    except IndexError:
        return idx, 0

def getWordSentimentValue(idx, word, pos):
    """
        This method will measure word senti degree based on sentiment rule
    """
    if pos[idx] == "Verba":
        return verbRule(idx, word, pos)
    elif pos[idx] == "Preposisi":
        return prepositionRule(idx, word, pos)
    elif pos[idx] == "Adjektiva":
        return idx, singleRule(word[idx])
    else:
        return idx, 0

def deleteSymbol(sentence):
    #Menghapus simbol
    symbol = ['”', '#', '$', '%', '&', '’', '(', ')', '*', '+','/', ':', ';', '<', '=', '>', '@', '[', "rt", ']', '^', '_', '`', '{', '|', '}', '~']
    for i in symbol : 
        sentence = sentence.replace(i, '')   
    return sentence

def deleteNumber(sentence):
    #Menghapus angka
    number = ['1','2','3','4','5','6','7','8','9','0']
    for i in number : 
        sentence = sentence.replace(i, '')   
    return sentence

def removeAffixNya(sentence): #bkn rule
    # Remove affixes nya except for word harus
    excep= ['harus', 'ha', 'ta']
    return ' '.join([word.replace("nya",'') for word in sentence.split(" ") if word not in excep])

def removeMentions(sentence): #bkn rule
    # Remove account mentions in sentence
    return removeAffixNya(' '.join([word for word in sentence.split(" ") if '@' not in word and 'http' not in word ]))

def preprocessing(sentence):
    sentence = removeMentions(str(sentence).lower())
    sentence = deleteSymbol(sentence)
    sentence = deleteNumber(sentence)
    return sentence


def dotAndCommaBreak(sentence):
    # Dot and Comma Break Rule
    sentence = removeMentions(str(sentence).lower().replace('.',',').replace('!',',').replace('?',',').replace('#','').replace("RT",''))
    return [word.strip() for word in sentence.split(',')]

def filtering(words):
    for word in words:
        if word in df_stopwords:
            words.remove(word)
    return words

def stemmingWord(word):
    word = stemmer.stem(' '.join(word))
    return word.split(" ")

def terimakasihPosition(sentence):
  # Check word terimakasih position in sentence
    try:
        try:
            if sentence.split(" ").index("terimakasih") == 0:
                return 1
        except ValueError:
            idxterima = sentence.split(" ").index("terima")
            idxkasih = sentence.split(" ").index("kasih")
            if idxterima+1 == idxkasih and idxterima == 0:
                return 1
    except:
        return 0


def anyFraseDuaKata(sentence):
    # Measure and check frase sentiment degree
    frasadf = pd.read_excel(filename, 'Frasa')
    frase = frasadf['word'].values.tolist()
    preponegatif = ["tidak", "belum", "anti", "bukan"]
    found = []
    try:
        sentence = sentence.split(" ")
        for idx, word in enumerate(sentence):
            twogram = sentence[idx]+' '+sentence[idx+1]
            if twogram in frase:
                sentimentfrase = frasadf.loc[frasadf["word"] == twogram, 'sentiment'].iloc[0]
                if sentence[idx-1] in preponegatif:
                    sentimentfrase = sentimentANDOperator(sentimentfrase, -1)
                found.append([twogram, sentimentfrase])
    except IndexError:
        pass
    return found


def checkFrase(sentence):
    # Measure and check frase sentiment degree
    check = anyFraseDuaKata(sentence)
    sentiment = 0
    if check != []:
        for item in check:
            sentence = sentence.replace(str(item[0]), "")
            sentiment += item[1]
        return sentiment, sentence
    return 0 

def normalizeSentimentVal(val):
    # Normalizing sentiment degree into three label
    # Positive (1), Negative (-1), Neutral (0)
    if val == 0: return 0
    elif val > 0: return 1
    else: return -1


def getSentiment(sentence, out):
    # Main method for get sentence sentiment degree
    totalsentiment = 0
    sentence_pre = preprocessing(sentence)
    sentencebreak = dotAndCommaBreak(sentence_pre)
    of = []
    ost = []
    sanitisinglist = ["se","begitu"]
    for istc, sentenceb in enumerate(sentencebreak):
        skipIndex = []
        sentimentval = 0
        if terimakasihPosition(sentenceb) == 1 and istc == 0:
            sentenceb.replace("terima", "")
            sentenceb.replace("kasih", "")
            sentimentval += 1
        try:
            sentimentfrase, sentenceb = checkFrase(sentenceb)
            sentimentval += sentimentfrase
        except TypeError:
            pass
        word = list(filter(None, sentenceb.split(" ")))
        #sanitising
        word = [item for item in word if item not in sanitisinglist]
        word = filtering(word)
        of.append(word)
        word = stemmingWord(word)
        ost.append(word)
        pos = convertSentence(' '.join(word))
        kalimat = []
        for idx,tag in enumerate(pos):
            if idx not in skipIndex and tag in pattern:
                issentiment, sentiment = getWordSentimentValue(idx,word,pos)
                if out == 2 :
                    ww = [word[idx], pos[idx], sentiment]
                    kalimat.append(' '.join(str(v) for v in ww))
                if issentiment is not None: 
                    sentimentval += sentiment
                    try: 
                        skipIndex = skipIndex + issentiment
                    except TypeError: 
                        skipIndex.append(issentiment)
                        continue
            else:
                continue
        totalsentiment += sentimentval
    if out == 1:
        re = [sentence_pre,', '.join(str(v) for v in of), ', '.join(str(v) for v in ost), normalizeSentimentVal(totalsentiment)]
        return re
    elif out == 2:
        re = [sentence_pre, ', '.join(str(v) for v in of), ', '.join(str(v) for v in ost), kalimat, normalizeSentimentVal(totalsentiment)]
        return re
    else :
        return normalizeSentimentVal(totalsentiment)

if __name__ == "__main__":
    app.run(debug=True)

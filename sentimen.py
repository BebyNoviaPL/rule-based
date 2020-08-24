from flask import Flask, render_template, request, redirect, url_for, flash, send_file, send_from_directory, safe_join, abort, jsonify
from werkzeug.utils import secure_filename
from flask_mysqldb import MySQL
import xlrd, xlwt
import os, pandas as pd, numpy as np, itertools, sys
from operator import itemgetter
from Sastrawi.Stemmer.StemmerFactory import StemmerFactory
import csv, string
import tweepy

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
    cur = mysql.connection.cursor()
    cur.execute("SELECT COUNT(IF( rule_baru = '1',rule_baru, NULL)) AS positif, COUNT(IF(rule_baru = '-1',rule_baru, NULL)) AS negatif, COUNT(IF( rule_baru = '0',rule_baru, NULL)) AS netral from training id WHERE id BETWEEN 401 and 800 UNION SELECT COUNT(IF( sentiment = '1',sentiment, NULL)) AS positif, COUNT(IF(sentiment = '-1',sentiment, NULL)) AS negatif, COUNT(IF( sentiment = '0',sentiment, NULL)) AS netral from data_testing id WHERE id_data BETWEEN 101 and 200")
    data = cur.fetchall()
    
    positif = 0 
    negatif = 0 
    netral = 0 
    for row in data:
        positif += row[0]
        negatif += row[1]
        netral += row[2]

    cur.execute("SELECT COUNT(IF( rule_baru = '1',rule_baru, NULL)) AS positif, COUNT(IF(rule_baru = '-1',rule_baru, NULL)) AS negatif, COUNT(IF( rule_baru = '0',rule_baru, NULL)) AS netral from training id WHERE id BETWEEN 1 and 400 UNION SELECT COUNT(IF( sentiment = '1',sentiment, NULL)) AS positif, COUNT(IF(sentiment = '-1',sentiment, NULL)) AS negatif, COUNT(IF( sentiment = '0',sentiment, NULL)) AS netral from data_testing id WHERE id_data BETWEEN 1 and 200")
    data = cur.fetchall()
   
    positif1 = 0 
    negatif1 = 0 
    netral1 = 0 
    for row in data:
        positif1 += row[0]
        negatif1 += row[1]
        netral1 += row[2]

    cur.close()
    return render_template('index.html', jmlh_sntmn=data,positif1=positif1,negatif1=negatif1,netral1=netral1,positif=positif,negatif=negatif,netral=netral)

@app.route('/update',methods=['POST','GET'])
def update():

    if request.method == 'POST':
        id_data = request.form['id_data']
        manual = request.form['manual']
        cur = mysql.connection.cursor()
        cur.execute("""
               UPDATE data_testing
               SET manual=%s
               WHERE id_data=%s
            """, ( manual, id_data))
       
        mysql.connection.commit()
        return redirect(url_for('craw'))

@app.route('/dataTraining')
def dataTraining():
    cur = mysql.connection.cursor()
    cur.execute("SELECT  * FROM training")
    data = cur.fetchall()
    cur.close()
    return render_template('dataTraining.html', menu='master', training=data )

@app.route('/prosesTraining')
def prosesTraining():
    cur = mysql.connection.cursor()
    cur.execute("SELECT  prep,filter,stemming FROM training")
    data = cur.fetchall()
    cur.close()
    return render_template('prosesTraining.html', menu='master', training=data )


@app.route('/perhitunganTraining')
def perhitunganTraining():
    cur = mysql.connection.cursor()
    cur.execute("SELECT kalimat,manual,rule_baru,rule_lama FROM training")
    data = cur.fetchall()
    cur.close()
    return render_template('perhitunganTraining.html', menu='master', training=data)

@app.route('/dataTraining/akurasiRule')
def google_pie_chart():
    cur = mysql.connection.cursor()
    cur.execute("SELECT  manual, rule_lama, rule_baru FROM training")
    dbData = cur.fetchall()
    cur.close()
        
    data = {
        'rule_baru_benar' : 0, 
        'rule_baru_salah' : 0, 
        'rule_lama_benar' : 0, 
        'rule_lama_salah' : 0
    }

    for rs in dbData:
        if rs[0] == rs[2]:
            data['rule_baru_benar'] = data['rule_baru_benar']+1
        else:
            data['rule_baru_salah'] = data['rule_baru_salah']+1

        if rs[0] == rs[1]:
            data['rule_lama_benar'] = data['rule_lama_benar']+1
        else:
            data['rule_lama_salah'] = data['rule_lama_salah']+1

    return render_template('akurasiRule.html', data=data)

@app.route('/dataTesting')
def dataTesting():
    cur = mysql.connection.cursor()
    cur.execute("SELECT  created, tweet FROM data_testing")
    data = cur.fetchall()
    cur.close()
    return render_template('dataTesting.html', menu='master', data_testing=data)

@app.route('/prosesTesting')
def prosesTesting():
    cur = mysql.connection.cursor()
    cur.execute("SELECT  prep,filter,stemming FROM data_testing")
    data = cur.fetchall()
    cur.close()
    return render_template('prosesTesting.html', menu='master', data_testing=data )


@app.route('/dataTesting/akurasi')
def akurasi():
    cur = mysql.connection.cursor()
    cur.execute("SELECT  tweet, sentiment, manual FROM data_testing")
    data = cur.fetchall()
    cur.close()
    return render_template('akurasi.html', menu='master', data_testing=data)

@app.route('/perhitungan')
def perhitungan():
    cur = mysql.connection.cursor()
    cur.execute("SELECT  tweet, kalimat, sentiment FROM data_testing")
    data = cur.fetchall()
    cur.close()
    return render_template('perhitungan.html', menu='master', data_testing=data)

@app.route('/ujiCoba')
def ujiCoba():
    cur = mysql.connection.cursor()
    cur.execute("SELECT  * FROM ujicoba")
    data = cur.fetchall()
    cur.close()
    return render_template('ujiCoba.html', menu='master', ujicoba=data )


@app.route('/addText', methods = ['POST'])
def addText():

    if request.method == "POST":
        flash("Data Inserted Successfully")
        tweet = request.form['tweet']
        manual = request.form['sentimen_manual']
        label = getSentiment(tweet, 5)
        cur = mysql.connection.cursor()
        cur.execute("INSERT INTO ujicoba (tweet,sentimen_manual, label) VALUES (%s,%s,%s)", (tweet,sentimen_manual,label))
        mysql.connection.commit()
        cur.close()
        return redirect(url_for('ujiCoba'))
    
def allowed_file(filename):
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


@app.route('/dataTraining/uploadTraining', methods=['GET', 'POST'])
def addTraining():
    if request.method == 'POST':
        # check if the post request has the file part
        if 'file' not in request.files:
            flash('No file part')
            return redirect(request.url)
        file = request.files['file']
        # if user does not select file, browser also
        # submit an empty part without filename
        if file.filename == '':
            flash('No selected file')
        if file and allowed_file(file.filename):
            filename = secure_filename("Data_Testing_Input.xlsx")
            os.remove(os.path.join(app.config['UPLOAD_FOLDER'], filename))
            file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
            # Clear data from data_testing
            
            #Insert new data to data_testing
            dat_file = xlrd.open_workbook(os.path.join(app.config['UPLOAD_FOLDER'], filename))
            dat_sheet = dat_file.sheet_by_index(0)
            jml_baris = dat_sheet.nrows
            cur = mysql.connection.cursor()
            cur.execute("TRUNCATE TABLE data_training")
            mysql.connection.commit()
            cur.close()
            for x in range(1,jml_baris):
                created_at = dat_sheet.cell_value(rowx=x, colx=0)
                tweet = dat_sheet.cell_value(rowx=x, colx=1)
                manual = dat_sheet.cell_value(rowx=x, colx=2)
                val = getSentiment(tweet, 2)
                prep = str(val[0])
                fil = str(val[1])
                stem = str(val[2])
                kal = str(val[3])
                rule_baru = str(val[4])
                
                cur = mysql.connection.cursor()
                cur.execute("""
                    INSERT INTO data_training (created, tweet, prep, filter, stemming, kalimat, manual, rule_baru) values (%s,%s,%s,%s,%s,%s,%s,%s)
                    """, (created_at, tweet, prep, fil, stem, kal, manual, rule_baru))
                mysql.connection.commit()
                cur.close()
            flash(1)
            return redirect(url_for('dataTraining'))
    return redirect(url_for('dataTraining'))

@app.route('/dataTesting/uploadTesting', methods=['GET', 'POST'])
def addTesting():
    if request.method == 'POST':
        # check if the post request has the file part
        if 'file' not in request.files:
            flash('No file part')
            return redirect(request.url)
        file = request.files['file']
        # if user does not select file, browser also
        # submit an empty part without filename
        if file.filename == '':
            flash('No selected file')
        if file and allowed_file(file.filename):
            filename = secure_filename("Data_Testing_Input.xlsx")
            os.remove(os.path.join(app.config['UPLOAD_FOLDER'], filename))
            file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
            # Clear data from data_testing
            
            #Insert new data to data_testing
            dat_file = xlrd.open_workbook(os.path.join(app.config['UPLOAD_FOLDER'], filename))
            dat_sheet = dat_file.sheet_by_index(0)
            jml_baris = dat_sheet.nrows
            cur = mysql.connection.cursor()
            cur.execute("TRUNCATE TABLE data_testing")
            mysql.connection.commit()
            cur.close()
            for x in range(1,jml_baris):
                created_at = dat_sheet.cell_value(rowx=x, colx=0)
                tweet = dat_sheet.cell_value(rowx=x, colx=1)
                manual = dat_sheet.cell_value(rowx=x, colx=2)
                val = getSentiment(tweet, 2)
                prep = str(val[0])
                fil = str(val[1])
                stem = str(val[2])
                kal = str(val[3])
                sentiment = str(val[4])
                cur = mysql.connection.cursor()
                cur.execute("""
                    INSERT INTO data_testing (created, tweet, prep, filter, stemming, kalimat, manual, sentiment) values (%s,%s,%s,%s,%s,%s,%s,%s)
                    """, (created_at, tweet, prep, fil, stem, kal, manual, sentiment))
                mysql.connection.commit()
                cur.close()
            flash(1)
            return redirect(url_for('dataTesting'))
    return redirect(url_for('dataTesting'))

@app.route('/dataTesting/akurasiRule')
def chart_testing():
    cur = mysql.connection.cursor()
    cur.execute("SELECT  manual, sentiment FROM data_testing")
    dbData = cur.fetchall()
    cur.close()
        
    data = {
        'testing_benar' : 0, 
        'testing_salah' : 0, 
        
    }

    for rs in dbData:
        if rs[0] == rs[1]:
            data['testing_benar'] = data['testing_benar']+1
        else:
            data['testing_salah'] = data['testing_salah']+1

     

    return render_template('akurasiRuleTesting.html', data=data)

@app.route('/dataTesting/downloadTesting')
def downloadTesting():
    filename = 'Data_Testing_Remake.xlsx'
    path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
    if not os.path.exists(path):
        cur = mysql.connection.cursor()
        cur.execute("SELECT  * FROM data_testing")
        data = cur.fetchall()
        cur.close()
        wb = xlwt.Workbook()
        ws = wb.add_sheet('Sentiment Word')

        header = ['No', 'Created', 'Tweet', 'Preposisi', 'Filter', 'Stemming', 'Kalimat', 'Sentiment', 'Manual']
        length_head = len(header)
        for x in range(length_head):
            ws.write(0, x, str(header[x]))

        i = 1
        for rs in data:
            ws.write(i, 0, i)
            for x in range(1, length_head):
                ws.write(i, x, rs[x])
            i+=1
        
        wb.save(path)
    return send_from_directory(directory=app.config['UPLOAD_FOLDER'], filename=filename, as_attachment=True)

@app.route('/dataTesting/Template')
def downloadTemplate():
    filename = 'templateTesting.xlsx'
    return send_from_directory(directory=app.config['UPLOAD_FOLDER'], filename=filename, as_attachment=True)

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

def adverbiaAdjectiveRule(idx, adverbsenti, datalist):
      # Measure advb + Adjective sentiment degree
    adjsenti = posdf.loc[posdf["word"] == datalist['words'][idx+1], 'sentiment'].iloc[0]
    return sentimentNANDOperator(adverbsenti,adjsenti)

def adverbiaVerbRule(idx, adverbsenti, datalist):
      # Measure advb + Verb sentiment degree
    isanyadjidx, verbsenti = verbRule(idx+1,datalist['words'], datalist['pos'])
    if isanyadjidx: # Check if there's any adjective after adverbia
        return isanyadjidx, sentimentNANDOperator(adverbsenti,verbsenti)
    return idx, sentimentNANDOperator(adverbsenti,verbsenti)

def adverbiaRule(idx, words, pos):
   
    datalist = {'words': words, 'pos': pos}
    adverbsenti =  posdf.loc[posdf["word"] == words[idx], 'sentiment'].iloc[0]
    try:
        if pos[idx+1] == "Adjektiva":
            return [idx+1], adverbiaAdjectiveRule(idx, adverbsenti, datalist)
        elif pos[idx+1] == "Verba":
            idxAdj, sentiment = adverbiaVerbRule(idx, adverbsenti, datalist)
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
    elif pos[idx] == "Adverbia":
        return adverbiaRule(idx, word, pos)
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


consumer_key = 'OmbxNeFsfcwrYhQYvsXm7TZiA'
consumer_secret = 'AgvJoa0d7BDdOXHa7gwDY9ROnOavRy44DZJMik0j64X8WdYXdm'
access_token = '3182546636-bNOfjdRbDG4ctm0WF9vl38wOaQsVRclah0I4lNN'
access_token_secret = 'xqWQFJHHus7KJJGu2GbPOrz55rUnylQg8X4ws3xaIczjm'

auth = tweepy.OAuthHandler(consumer_key, consumer_secret)
auth.set_access_token(access_token, access_token_secret)
api = tweepy.API(auth,wait_on_rate_limit=True)

@app.route('/craw')
def craw():
    cur = mysql.connection.cursor()
    cur.execute("SELECT id_data, created, tweet, sentiment,manual FROM data_testing")
    data = cur.fetchall()
    cur.close()
    return render_template('crawling.html', menu='master', data=data)


@app.route('/crawling', methods=['POST'])
def crawling():
    query = str(request.form['query'])
    jumlah = int(request.form['jumlah'])
    for tweet in tweepy.Cursor(api.search,q=query,
                           lang="id",
                           since="2019-04-03").items(jumlah):
        tweets = tweet.text
        created_at = tweet.created_at
        print(tweets)
        label = getSentiment(tweets, 5)
        cur = mysql.connection.cursor()
        cur.execute("INSERT INTO data_testing (created,tweet,sentiment) VALUES (%s,%s,%s)", (created_at,tweets,label))
        mysql.connection.commit()
        cur.close()
    return redirect(url_for('craw'))





if __name__ == "__main__":
    app.run(debug=True)

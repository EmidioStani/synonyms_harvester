"""
.. module:: synonyms_harvester
   :platform: Unix, Windows
   :synopsis: A python script to enrich a skos list with synonyms taken from different sources
.. moduleauthor:: Emidio Stani <emidio.stani@pwc.com>
"""


import argparse
import re
import time

import nltk
import requests
import simplejson
import spacy
from datamuse import datamuse
from nltk.tokenize import WhitespaceTokenizer
from rdflib import Graph, Literal, Namespace, URIRef
from rdflib.namespace import RDF, SKOS
from rdflib.paths import mul_path
from SPARQLWrapper import JSON, SPARQLWrapper

nlp = spacy.load("en_core_web_lg")

nltk.download('wordnet')
nltk.download('averaged_perceptron_tagger')
nltk.download('punkt')
nltk.download('stopwords')
from statistics import mean

import html2text
import jieba
import nltk.data
import numpy as np
from bs4 import BeautifulSoup
from gensim import corpora, models, similarities
from nltk import word_tokenize
from nltk.corpus import stopwords, wordnet
from nltk.stem import WordNetLemmatizer
from nltk.tokenize import RegexpTokenizer
from stop_words import get_stop_words


def synonymsWiktionary(term, filename):
    g2 = Graph()
    ns1 = Namespace("http://www.w3.org/2004/02/skos/core#")
    g2.parse(filename, format="turtle")
    for s, p, o in g2.triples((None, RDF.type, ns1.Concept)):
        for a, b, c in g2.triples((s, ns1.prefLabel, None)):
            if term.strip().lower() == c.strip().lower():
                # print("Found term in Wiktionary %s"  %c)
                return g2.triples((s, ns1.altLabel, None))


def synonymsFromSPARQLEndpoint(endpoint, term):
    sparql = SPARQLWrapper(endpoint)
    sparql.setQuery("""
        PREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#>
        PREFIX skos: <http://www.w3.org/2004/02/skos/core#>
        SELECT ?altlabel
        WHERE {
            ?term rdf:type skos:Concept .
            ?term skos:prefLabel ?termlabel .
            ?term skos:altLabel ?altlabel .
            FILTER (lcase(?termlabel) = '""" + term.lower() + """'@en)
            FILTER(lang(?altlabel)="en" || lang(?altlabel)="")
        }
        """)

    sparql.setReturnFormat(JSON)
    results = sparql.query().convert()
    resultslist = []
    for result in results["results"]["bindings"]:
        label = result["altlabel"]["value"]
        label = label.lower().replace("_", " ")
        resultslist.append(label)

    return resultslist

def synonymsFromCosineSPARQLEndpoint(endpoint, term):
    sparql = SPARQLWrapper(endpoint)
    sparql.setQuery("""
        PREFIX xsd: <http://www.w3.org/2001/XMLSchema#>
        PREFIX jsfn:<http://www.ontotext.com/js#>
        PREFIX skos: <http://www.w3.org/2004/02/skos/core#>

        SELECT ?altlabel ?sim
        WHERE {
            SELECT ?label ?altlabel ?sim
            WHERE {
                ?s skos:prefLabel ?label . 
                ?s skos:altLabel ?altlabel .
                BIND('""" + term.lower() + """'@en as ?label2)
                FILTER(lang(?altlabel)="en" || lang(?altlabel)="")
                BIND(jsfn:textCosineSimilarity(lcase(str(?label)), str(?label2)) as ?sim)
                FILTER(?sim > 0.7 && str(?sim) != "NaN")
            }
        }
        ORDER BY DESC(?sim)
        """)

    sparql.setReturnFormat(JSON)
    results = sparql.query().convert()
    resultslist = []
    for result in results["results"]["bindings"]:
        label = result["altlabel"]["value"]
        if not label.isupper():
            label = label.lower()
        label = label.replace("_", " ")
        resultslist.append(label)

    return resultslist


def synonymsWordNet2(term):
    return synonymsFromSPARQLEndpoint("http://localhost:7200/repositories/wordnet-synonyms", term)

def synonymsUnesco(term):
    return synonymsFromSPARQLEndpoint("http://localhost:7200/repositories/unesco", term)

def synonymsFIBO(term):
    return synonymsFromSPARQLEndpoint("http://localhost:7200/repositories/fibo", term)

def synonymsSTW(term):
    return synonymsFromSPARQLEndpoint("http://localhost:7200/repositories/stw", term)

def synonymsLCSH(term):
    return synonymsFromSPARQLEndpoint("http://localhost:7200/repositories/lcsh", term)

def synonymsWordNet2J(term):
    return synonymsFromCosineSPARQLEndpoint("http://localhost:7200/repositories/wordnet-synonyms", term)

def synonymsUnescoJ(term):
    return synonymsFromCosineSPARQLEndpoint("http://localhost:7200/repositories/unesco", term)

def synonymsFIBOJ(term):
    return synonymsFromCosineSPARQLEndpoint("http://localhost:7200/repositories/fibo", term)

def synonymsSTWJ(term):
    return synonymsFromCosineSPARQLEndpoint("http://localhost:7200/repositories/stw", term)

def synonymsLCSHJ(term):
    return synonymsFromCosineSPARQLEndpoint("http://localhost:7200/repositories/lcsh", term)


def synonymsDatamuse(term, max):
    api = datamuse.Datamuse()
    response = api.words(ml=term.lower())
    resultslist = []
    counter = 0
    for i in response:
        if(i.get('tags') and ('syn' in i['tags'])):
            if(counter < max):
                word = i['word'].lower().replace("_", " ")
                resultslist.append(word)
                counter += 1
            else:
                break
    if(len(resultslist) == 0 and len(response) > 0):
        counter2 = 0
        maxwords = min(5, len(response))
        for i in response:
            if (i.get('tags') and ('ant' not in i['tags'])):
                if(counter2 < maxwords):
                    word = i['word'].lower().replace("_", " ")
                    resultslist.append(word)
                    counter2 += 1
                else:
                    break
    return resultslist


def synonymsAltervista(term, apikey):
    endpoint = 'http://thesaurus.altervista.org/thesaurus/v1'
    word = '?word=' + term
    language = '&language=' + 'en_US'
    key = '&key=' + apikey
    output = '&output=' + 'json'
    url = endpoint + word + language + key + output
    arrayWithoutAntonyms = []
    try:
        response = requests.get(url).json()
        # print(response)
        syns = ''
        if 'error' not in response:
            for i in response['response']:
                # if i['list']['category'] == '(noun)':
                syns = syns + i['list']['synonyms'] + '|'
            arraylist = syns.split("|")
            arraylist = [a for a in arraylist if a]
            # arraylist = [re.sub(r' \(generic term\)', r'', a) for a in arraylist]
            arraylist = [re.sub(r' \(related term\)', r'', a) for a in arraylist]
            arraylist = [re.sub(r' \(similar term\)', r'', a) for a in arraylist]
            arraylist = [a.replace("_", " ") for a in arraylist]
            lower_case_list = []
            for a in arraylist:
                if not a.isupper():
                    a = a.lower()
                lower_case_list.append(a)
            arrayWithoutGenericTerms = [x for x in lower_case_list if 'generic term' not in x]
            arrayWithoutAntonyms = [x for x in arrayWithoutGenericTerms if 'antonym' not in x]
    except requests.exceptions.RequestException as e:
        print(e)
    return arrayWithoutAntonyms

def get_wordnet_pos(treebank_tag):

    if treebank_tag.startswith('J'):
        return wordnet.ADJ
    elif treebank_tag.startswith('V'):
        return wordnet.VERB
    elif treebank_tag.startswith('N'):
        return wordnet.NOUN
    elif treebank_tag.startswith('R'):
        return wordnet.ADV
    else:
        return ''
	
def timer(start, end):
    hours, rem = divmod(end-start, 3600)
    minutes, seconds = divmod(rem, 60)
    print("{:0>2}:{:0>2}:{:05.2f}".format(int(hours), int(minutes), seconds))

def checkExactMatch(c, wik_file, eurovoc_file):
        x= []
        print("Searching in Wiktionary")
        syns2 = synonymsWiktionary(c, wik_file)
        if(syns2):
            for a, b, z in syns2:
                print("Adding alternative label %s" % z)
                x.append(str(z))
        print("Searching in Wordnet")
        syns3 = None
        syns3 = synonymsWordNet2(c)
        if(syns3):
            for z in syns3:
                print("Adding alternative label %s" % z)
                x.append(z)
        print("Searching in Unesco")
        syns6 = None
        syns6 = synonymsUnesco(c)
        if(syns6):
            for z in syns6:
                print("Adding alternative label %s" % z)
                x.append(z)
        print("Searching in FIBO")
        syns7 = None
        syns7 = synonymsFIBO(c)
        if(syns7):
            for z in syns7:
                print("Adding alternative label %s" % z)
                x.append(z)
        print("Searching in STW")
        syns8 = None
        syns8 = synonymsSTW(c)
        if(syns8):
            for z in syns8:
                print("Adding alternative label %s" % z)
                x.append(z)
        print("Searching in LCSH")
        syns9 = None
        syns9 = synonymsLCSH(c)
        if(syns9):
            for z in syns9:
                print("Adding alternative label %s" % z)
                x.append(z)
        print("Searching in Eurovoc")
        syns10 = synonymsWiktionary(c, eurovoc_file)
        if(syns10):
            for a, b, z in syns10:
                print("Adding alternative label %s" % z)
                x.append(str(z))
        return x

def checkCosineMatch(c):
        x= []
        tokenizer = RegexpTokenizer(r'[\w\-]+')
        tokens = tokenizer.tokenize(c.lower())
        short_list = []
        for token in tokens:
            if (len(token) >= 5): #media no, policy no, monetary yes, manufacturing yes, technology yes
                short_list.append(token)
        
        for token in short_list:
            if(len(short_list) > 0):
                print("Searching for %s" % token)
                print("Searching in Wordnet")
                syns3 = None
                syns3 = synonymsWordNet2J(token)
                if(syns3):
                    for z in syns3:
                        print("Adding alternative label %s" % z)
                        x.append(z)
                print("Searching in Unesco")
                syns6 = None
                syns6 = synonymsUnescoJ(token)
                if(syns6):
                    for z in syns6:
                        print("Adding alternative label %s" % z)
                        x.append(z)
                print("Searching in FIBO")
                syns7 = None
                syns7 = synonymsFIBOJ(token)
                if(syns7):
                    for z in syns7:
                        print("Adding alternative label %s" % z)
                        x.append(z)
                print("Searching in STW")
                syns8 = None
                syns8 = synonymsSTWJ(token)
                if(syns8):
                    for z in syns8:
                        print("Adding alternative label %s" % z)
                        x.append(z)
                print("Searching in LCSH")
                syns9 = None
                syns9 = synonymsLCSHJ(token)
                if(syns9):
                    for z in syns9:
                        print("Adding alternative label %s" % z)
                        x.append(z)
        return x

def getNouns(c):
    tokenizer = RegexpTokenizer(r'[\w\-]+')
    tokens = tokenizer.tokenize(c.lower())
    print("tokens %s" % tokens)
    filtered_sentence = [w for w in tokens if not w in stop_words]
    print("filtered_sentence %s" % filtered_sentence)
    post_tags = nltk.pos_tag(filtered_sentence)
    print("post_tags %s" % post_tags)
    # https://stackoverflow.com/questions/40167612/how-to-keep-only-the-noun-words-in-a-wordlist-python-nltk
    nouns = list(set([word for word,pos in post_tags if (pos == 'NN' or pos == 'NNP' or pos == 'NNS' or pos == 'NNPS')]))
    print("nouns %s" % nouns)
    return nouns

def getVerbs(c):
    tokenizer = RegexpTokenizer(r'[\w\-]+')
    tokens = tokenizer.tokenize(c.lower())
    print("tokens %s" % tokens)
    filtered_sentence = [w for w in tokens if not w in stop_words]
    print("filtered_sentence %s" % filtered_sentence)
    post_tags = nltk.pos_tag(filtered_sentence)
    print("post_tags %s" % post_tags)
    # https://stackoverflow.com/questions/40167612/how-to-keep-only-the-noun-words-in-a-wordlist-python-nltk
    verbs = list(set([word for word,pos in post_tags if (pos == 'VB' or pos == 'VBD' or pos == 'VBN' or pos == 'VBG' or pos == 'VBP')]))
    print("verbs %s" % verbs)
    return verbs

def checkLemmas(nouns, wik_file, eurovoc_file):
    x= []
    for noun in nouns:
        lemma =  lemmatizer.lemmatize(noun)
        print(noun, "=>", lemma)
        x.extend(checkExactMatch(lemma, wik_file, eurovoc_file))
    return x

def checkVerbsLemmas(verbs, wik_file, eurovoc_file):
    x= []
    for verb in verbs:
        lemma =  lemmatizer.lemmatize(verb, pos="v")
        print(verb, "=>", lemma)
        x.extend(checkExactMatch(lemma, wik_file, eurovoc_file))
    return x

def getWords(c):
    tokenizer = RegexpTokenizer(r'[\w\-]+')
    tokens = tokenizer.tokenize(c.lower())
    filtered_sentence = [w for w in tokens if not w in stop_words]
    print("filtered_sentence %s" % filtered_sentence)
    return filtered_sentence

def getMaxSimilarity(element, name, dictionary, tfidf, corpus, feature_cnt):
    kw_vector = dictionary.doc2bow(jieba.lcut(element))
    index = similarities.SparseMatrixSimilarity(tfidf[corpus], num_features = feature_cnt)
    sim = index[tfidf[kw_vector]]
    arr1 = np.array(sim)
                
    # https://thispointer.com/find-max-value-its-index-in-numpy-array-numpy-amax/
    maxSimilarity = np.amax(arr1)
    print('Element %s has Max similarity in %s %s ' % (element, name, maxSimilarity))
    return maxSimilarity

def similar(element, arrayElements):
    listSim = []
    for myelem in arrayElements:
        doc1 = nlp(element)
        doc2 = nlp(myelem)
        listSim.append(doc1.similarity(doc2))
    max_similarity = max(listSim)
    if (max_similarity > 0.7):
        max_index = listSim.index(max_similarity)
        max_value = arrayElements[max_index]
        print('Element %s has the max similarity %s with  %s' % (element, max_similarity, max_value))
        return max_value
    else:
        return None


def getAverageFromList(element, arraySim):
    list_sim = []
    for index in range(len(arraySim)):
        name= arraySim[index]["name"]
        data= arraySim[index]["data"]
        dict= arraySim[index]["dictionary"]
        tfidf = arraySim[index]["tfidf"]
        corpus= arraySim[index]["corpus"]
        feature_cnt = arraySim[index]["feature_cnt"]
        max_sim = 0
        try:
            for mylist1 in data:
                for mylist2 in mylist1:
                    if element == mylist2:
                        print('found element %s in %s' % (element, name))
                        max_sim = 1
                        raise StopIteration
        except StopIteration: pass
        if max_sim == 0:
            max_sim = getMaxSimilarity(element, name, dict, tfidf, corpus, feature_cnt)
        list_sim.append(max_sim)

    average = np.mean(list_sim)
    return average

ALTERVISTA_KEY = 'Kdnuiqz85LO7gGIHdGZf'
WIKTIONARY_FILE = 'syn_wiktionary_2.ttl'
EUROVOC_FILE = 'syn_eurovoc.ttl'
INPUT_FILE = 'annexI-2021-12-20.ttl'
OUTPUT_FILE = 'output_7.ttl'
PARSER = argparse.ArgumentParser(description="Enrich skos list with synonyms")
PARSER.add_argument("-k", "--apikey", help="api key for Altervista")
PARSER.add_argument("-w", "--wiktionaryfile", help="syn file for wikitionary")
PARSER.add_argument("-e", "--eurovocfile", help="syn file for eurovoc")
PARSER.add_argument("-i", "--input", help="input file in RDF/XML")
PARSER.add_argument("-o", "--output", help="output file in Turtle")
ARGS = PARSER.parse_args()

if ARGS.apikey:
    ALTERVISTA_KEY = ARGS.apikey
if ARGS.wiktionaryfile:
    WIKTIONARY_FILE = ARGS.wiktionaryfile
if ARGS.eurovocfile:
    EUROVOC_FILE = ARGS.eurovocfile
if ARGS.input:
    INPUT_FILE = ARGS.input
if ARGS.output:
    OUTPUT_FILE = ARGS.output
start = time.time()
SKOSXL = Namespace("http://www.w3.org/2008/05/skos-xl#")
g = Graph()
g.parse(INPUT_FILE , format="ttl")
lemmatizer = WordNetLemmatizer()
#stop_words = set(stopwords.words('english')) 
stop_words = list(get_stop_words('en'))         #Have around 900 stopwords
nltk_words = list(stopwords.words('english'))   #Have around 150 stopwords
stop_words.extend(nltk_words)

# https://medium.com/better-programming/introduction-to-gensim-calculating-text-similarity-9e8b55de342d

listSim = []

html = open("services_in_the_internal_market.html").read()
soup = BeautifulSoup(html, 'html.parser') 
data = soup.get_text()
# data = html2text.html2text(html)
tokenizer = nltk.data.load('tokenizers/punkt/english.pickle')
texts = tokenizer.tokenize(data)
texts_cut = [jieba.lcut(text) for text in texts]
dictionary = corpora.Dictionary(texts_cut)
feature_cnt = len(dictionary.token2id)
corpus = [dictionary.doc2bow(text) for text in texts_cut]
tfidf = models.TfidfModel(corpus)

internal_market = {
    "name" : "internal_market",
    "data" : texts_cut,
    "dictionary" : dictionary,
    "feature_cnt" : feature_cnt,
    "corpus" : corpus,
    "tfidf" : tfidf
}

listSim.append(internal_market.copy())

html2 = open("establishing_single_digital_gateway.html",  encoding="utf8").read()
soup2 = BeautifulSoup(html2, 'html.parser') 
data2 = soup2.get_text()
tokenizer2 = nltk.data.load('tokenizers/punkt/english.pickle')
texts2 = tokenizer.tokenize(data2)
texts_cut2 = [jieba.lcut(text) for text in texts2]
dictionary2 = corpora.Dictionary(texts_cut2)
feature_cnt2 = len(dictionary2.token2id)
corpus2 = [dictionary2.doc2bow(text) for text in texts_cut2]
tfidf2 = models.TfidfModel(corpus2) 

digital_gateway = {
    "name" : "digital_gateway",
    "data" : texts_cut2,
    "dictionary" : dictionary2,
    "feature_cnt" : feature_cnt2,
    "corpus" : corpus2,
    "tfidf" : tfidf2
}

listSim.append(digital_gateway.copy())

html3 = open("gdpr.html",  encoding="utf8").read()
soup3 = BeautifulSoup(html3, 'html.parser') 
data3 = soup3.get_text()
tokenizer3 = nltk.data.load('tokenizers/punkt/english.pickle')
texts3 = tokenizer.tokenize(data3)
texts_cut3 = [jieba.lcut(text) for text in texts3]
dictionary3 = corpora.Dictionary(texts_cut3)
feature_cnt3 = len(dictionary3.token2id)
corpus3 = [dictionary3.doc2bow(text) for text in texts_cut3]
tfidf3 = models.TfidfModel(corpus3) 

gdpr = {
    "name" : "gdpr",
     "data" : texts_cut3,
    "dictionary" : dictionary3,
    "feature_cnt" : feature_cnt3,
    "corpus" : corpus3,
    "tfidf" : tfidf3
}

listSim.append(gdpr.copy())


for s, p, o in sorted(g.triples((None, RDF.type, SKOS.Concept))):
    for d, e, f in g.triples((s, SKOSXL.prefLabel, None)): 
        for a, b, c in sorted(g.triples((f, SKOSXL.literalForm , None))):
            total_syns = 0
            print("%s has label %s" % (a, c))
            c = c.replace('Union', '')
            c = c.replace('Member', '')
            #c = c.replace('&', ' ')
            #tokens = word_tokenize(c.lower())
            # syns = synonymsThesaurus(c.lower())
            # for synonym in syns:
            #    print(synonym.text)
            #    g.add( (a, SKOS.altLabel, Literal(synonym.text, lang="en")) )
            mylist = []
            mylist2 = []
            mylist = list(set(mylist))

            print("1. Searching in Datamuse...")
            syns4 = synonymsDatamuse(c, 10)
            if(syns4):
                for z in syns4:
                    print("Adding alternative label %s" % z)
                    mylist.append(z)

            
            words = getWords(c)
            if len(words) < 5:
                print("2. Searching for %s exact match..." % c)
                list2 = checkExactMatch(c,WIKTIONARY_FILE, EUROVOC_FILE)
                mylist.extend(list2)

            nouns = getNouns(c)
            lenNouns = len(nouns)


            print("3. Checking noun with %s lemmas..." % lenNouns)
            list2 = checkLemmas(nouns,WIKTIONARY_FILE, EUROVOC_FILE)
            mylist.extend(list2)

            for noun in nouns:
                print("4. Searching %s in Altervista..." % noun)
                syns5 = synonymsAltervista(noun, ALTERVISTA_KEY)
                if(syns5):
                    for z in syns5:
                        print("Adding alternative label %s" % z)
                        mylist.append(z)
            
            verbs = getVerbs(c)
            lenVerbs = len(verbs)

            print("5. Checking verbs with %s lemmas..." % lenVerbs)
            list2 = checkVerbsLemmas(verbs,WIKTIONARY_FILE, EUROVOC_FILE)
            mylist.extend(list2)
            
            for verb in verbs:
                print("6. Searching verb %s in Altervista..." % verb)
                syns5 = synonymsAltervista(verb, ALTERVISTA_KEY)
                if(syns5):
                    for z in syns5:
                        print("Adding alternative label %s" % z)
                        mylist.append(z)
            
            print("7. Checking cosine distance...")
            list2 = checkCosineMatch(c)
            mylist.extend(list2)
            
            print("8. Filtering")
            new_strings = []
            for string in mylist:
                new_string = string.replace("_", " ")
                new_strings.append(new_string)
            mylist = list(set(new_strings))

            for temp in mylist:
                if(getAverageFromList(temp, listSim) > 0):
                    mylist2.append(temp)
            mylist2 = list(set(mylist2))
            print(mylist2)
            mylist = mylist2
                # mylist2 = []


            # removing elements containing the following characters
            test_str="'.%"
            res = []
            for sub in mylist:
                flag = 0
                if len(sub) < 4:
                    flag = 1
                    print('Element %s will removed from the list' % (sub) )
                else:
                    for ele in sub:
                        if ele in test_str:
                            flag = 1
                            print('Element %s will removed from the list' % (sub) )

                if not flag:
                    res.append(sub)
            
            mylist2 = []
            mylist3 = []
            mytemplist4 = []
            mylist5 = []
            for element in res:
                """
                kw_vector = dictionary.doc2bow(jieba.lcut(element))
                index = similarities.SparseMatrixSimilarity(tfidf[corpus], num_features = feature_cnt)
                sim = index[tfidf[kw_vector]]
                arr1 = np.array(sim)
                
                # https://thispointer.com/find-max-value-its-index-in-numpy-array-numpy-amax/
                maxSimilarity = np.amax(arr1)
                print('Element %s has Max similarity in internal market %s ' % (element, maxSimilarity))
                
                kw_vector2 = dictionary2.doc2bow(jieba.lcut(element))
                index2 = similarities.SparseMatrixSimilarity(tfidf2[corpus2], num_features = feature_cnt2)
                sim2 = index2[tfidf2[kw_vector2]]
                arr2 = np.array(sim2)
                maxSimilarity2 = np.amax(arr2)
                print('Element %s has Max similarity in digital single gateway %s ' % (element, maxSimilarity2))

                kw_vector3 = dictionary3.doc2bow(jieba.lcut(element))
                index3 = similarities.SparseMatrixSimilarity(tfidf3[corpus3], num_features = feature_cnt3)
                sim3 = index3[tfidf3[kw_vector3]]
                arr3 = np.array(sim3)
                maxSimilarity3 = np.amax(arr3)
                print('Element %s has Max similarity in gdpr %s ' % (element, maxSimilarity3))

                list_sim = [maxSimilarity, maxSimilarity2, maxSimilarity3]
                average = np.mean(list_sim)
                """
                
                average = getAverageFromList(element, listSim)
                a_dictionary = {"element" : element, "average" : average}
                if(average > 0):
                    mylist3.append(a_dictionary)
                #    result = np.where(arr1 == np.amax(arr1))
                #    print('Returned tuple of arrays :', result)
                #    print('List of Indices of maximum element :', result[0])
                #    print('text: ', texts[result[0][0].astype(int)])
            length_list = len(mylist3)
            if (length_list > 40):
                leftover = length_list - 40
                mylist3 = sorted(mylist3, key = lambda i: i['average'],reverse=True)
                mylist3 = mylist3[:-leftover or None]
            mylist3 = sorted(mylist3, key = lambda i: i['average'],reverse=True)
            print(mylist3)
            for mydict in mylist3:
                mylist2.append(mydict["element"])

            print("Searching similarities...")

            res = [d for d in mylist3 if d['average'] > 0.6]
            left_over = [d for d in mylist3 if d['average'] < 0.6]
            left_over_list = []
            for mydict in res:
                get_elem = mydict["element"]
                mylist5.append(get_elem)
                print('Element %s is appended to the list' % (get_elem) )
            for mydict in left_over:
                get_elem = mydict["element"]
                left_over_list.append(get_elem)
                print('Element %s is appended to the left over list' % (get_elem) )

            print(mylist5)
            len5 = len(mylist5)
            len6 = len(left_over_list)
            final_list = []
            mywords = getWords(c)
            last_words = [x for x in left_over_list if x not in mywords]
            if (len5 > 0 and len6 > 0):
                for myword in mywords:
                    print("searching in mywords")
                    if(len(last_words) == 0):
                        break
                    else:
                        most_similar_elem = similar(myword, last_words)
                        if(most_similar_elem is not None):
                            last_words.remove(most_similar_elem)
                            mylist5.append(most_similar_elem)
                            print(mylist5)
                for myelem in mylist5:
                    print("searching in mylist5")
                    # myelem = mylist5[index]
                    if(len(last_words) == 0):
                        break
                    else:
                        most_similar_elem = similar(myelem, last_words)
                        if(most_similar_elem is not None):
                            last_words.remove(most_similar_elem)
                            mylist5.append(most_similar_elem)
                            print(mylist5)
                final_list = mylist5.copy()
            else:
                final_list = mylist2.copy()
            # result = np.where(arr1 == np.amax(arr1))
            #print('Returned tuple of arrays :', result)
            # print('List of Indices of maximum element :', result[0])
            #print('text: ', texts[result[0][0].astype(int)])
            
            for element in final_list:
                labelURI = element.replace(" ","-").replace("(","-").replace(")","-").replace(",","-").replace("*","-").replace("&amp;","-").replace(".","-").replace("'","-")
                altLabelURI = URIRef("http://publications.europa.eu/resource/authority/publicservice-theme/label/" + labelURI)
                g.add((s, SKOSXL.altLabel, altLabelURI))
                g.add((altLabelURI, SKOSXL.literalForm, Literal(element, lang="en")))
g.serialize(destination=OUTPUT_FILE, format='turtle')
end = time.time()
timer(start, end)

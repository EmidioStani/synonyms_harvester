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
from datamuse import datamuse
from nltk.tokenize import WhitespaceTokenizer
from rdflib import Graph, Literal, Namespace, URIRef
from rdflib.namespace import RDF, SKOS
from SPARQLWrapper import JSON, SPARQLWrapper

nltk.download('wordnet')
nltk.download('averaged_perceptron_tagger')
nltk.download('punkt')
nltk.download('stopwords')
from statistics import mean

import html2text
import jieba
import nltk.data
import numpy as np
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
            arraylist = [re.sub(r' \(generic term\)', r'', a) for a in arraylist]
            arraylist = [re.sub(r' \(related term\)', r'', a) for a in arraylist]
            arraylist = [a.replace("_", " ") for a in arraylist]
            lower_case_list = []
            for a in arraylist:
                if not a.isupper():
                    a = a.lower()
                lower_case_list.append(a)
            arrayWithoutAntonyms = [x for x in lower_case_list if 'antonym' not in x]
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

def checkExactMatch(c, wik_file):
        x= []
        print("Searching in Wiktionary")
        syns2 = synonymsWiktionary(c, wik_file)
        if(syns2):
            for a, b, z in syns2:
                print("Adding alternative label %s" % z)
                x.append(z)
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
        return x

def checkCosineMatch(c, wik_file):
        x= []
        tokenizer = RegexpTokenizer(r'[\w\-]+')
        tokens = tokenizer.tokenize(c.lower())
        short_list = []
        for token in tokens:
            if (len(token) >= 8): #media no, policy no, monetary yes, manufacturing yes, technology yes
                short_list.append(token)
        short_list_str = ' '.join(short_list)
        if(len(short_list_str) > 0):
            print("Searching for %s" % short_list_str)
            print("Searching in Wordnet")
            syns3 = None
            syns3 = synonymsWordNet2J(short_list_str)
            if(syns3):
                for z in syns3:
                    print("Adding alternative label %s" % z)
                    x.append(z)
            print("Searching in Unesco")
            syns6 = None
            syns6 = synonymsUnescoJ(short_list_str)
            if(syns6):
                for z in syns6:
                    print("Adding alternative label %s" % z)
                    x.append(z)
            print("Searching in FIBO")
            syns7 = None
            syns7 = synonymsFIBOJ(short_list_str)
            if(syns7):
                for z in syns7:
                    print("Adding alternative label %s" % z)
                    x.append(z)
            print("Searching in STW")
            syns8 = None
            syns8 = synonymsSTWJ(short_list_str)
            if(syns8):
                for z in syns8:
                    print("Adding alternative label %s" % z)
                    x.append(z)
            print("Searching in LCSH")
            syns9 = None
            syns9 = synonymsLCSHJ(short_list_str)
            if(syns9):
                for z in syns9:
                    print("Adding alternative label %s" % z)
                    x.append(z)
        return x

def checkLemmas(c, wik_file, max_num_nouns):
    x= []
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
    if(len(nouns) == max_num_nouns):
        for noun in nouns:
            lemma =  lemmatizer.lemmatize(noun)
            print(noun, "=>", lemma)
            if(lemma != c.lower()):  # skip the case of 1 word which is equal to the lemma and thus already checked in the exact match
                x.extend(checkExactMatch(lemma, wik_file))

    return x


ALTERVISTA_KEY = 'Kdnuiqz85LO7gGIHdGZf'
WIKTIONARY_FILE = 'syn_wiktionary_2.ttl'
INPUT_FILE = 'sample2.rdf'
OUTPUT_FILE = 'output_3.ttl'
PARSER = argparse.ArgumentParser(description="Enrich skos list with synonyms")
PARSER.add_argument("-k", "--apikey", help="api key for Altervista")
PARSER.add_argument("-w", "--wiktionaryfile", help="syn file for wikitionary")
PARSER.add_argument("-i", "--input", help="input file in RDF/XML")
PARSER.add_argument("-o", "--output", help="output file in Turtle")
ARGS = PARSER.parse_args()

if ARGS.apikey:
    ALTERVISTA_KEY = ARGS.apikey
if ARGS.wiktionaryfile:
    WIKTIONARY_FILE = ARGS.wiktionaryfile
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

html = open("services_in_the_internal_market.html").read()
data = html2text.html2text(html)
tokenizer = nltk.data.load('tokenizers/punkt/english.pickle')
texts = tokenizer.tokenize(data)
texts_cut = [jieba.lcut(text) for text in texts]
dictionary = corpora.Dictionary(texts_cut)
feature_cnt = len(dictionary.token2id)
corpus = [dictionary.doc2bow(text) for text in texts_cut]
tfidf = models.TfidfModel(corpus)

html2 = open("establishing_single_digital_gateway.html",  encoding="utf8").read()
data2 = html2text.html2text(html2)
tokenizer2 = nltk.data.load('tokenizers/punkt/english.pickle')
texts2 = tokenizer.tokenize(data2)
texts_cut2 = [jieba.lcut(text) for text in texts2]
dictionary2 = corpora.Dictionary(texts_cut2)
feature_cnt2 = len(dictionary2.token2id)
corpus2 = [dictionary2.doc2bow(text) for text in texts_cut2]
tfidf2 = models.TfidfModel(corpus2) 


html3 = open("gdpr.html",  encoding="utf8").read()
data3 = html2text.html2text(html3)
tokenizer3 = nltk.data.load('tokenizers/punkt/english.pickle')
texts3 = tokenizer.tokenize(data3)
texts_cut3 = [jieba.lcut(text) for text in texts3]
dictionary3 = corpora.Dictionary(texts_cut3)
feature_cnt3 = len(dictionary3.token2id)
corpus3 = [dictionary3.doc2bow(text) for text in texts_cut3]
tfidf3 = models.TfidfModel(corpus3) 


for s, p, o in sorted(g.triples((None, RDF.type, SKOS.Concept))):
    for d, e, f in g.triples((s, SKOSXL.prefLabel, None)): 
        for a, b, c in sorted(g.triples((f, SKOSXL.literalForm , None))):
            total_syns = 0
            print("%s has label %s" % (a, c))
            
            #c = c.replace('&', ' ')
            #tokens = word_tokenize(c.lower())
            # syns = synonymsThesaurus(c.lower())
            # for synonym in syns:
            #    print(synonym.text)
            #    g.add( (a, SKOS.altLabel, Literal(synonym.text, lang="en")) )
            mylist = []
            mylist = checkExactMatch(c,WIKTIONARY_FILE)

            mylist = list(set(mylist))
            print("Checking term with 1 lemmas...")
            list2 = checkLemmas(c,WIKTIONARY_FILE, 1)
            mylist.extend(list2)

            mylist = list(set(mylist))
 
            print("Searching in Datamuse")
            syns4 = synonymsDatamuse(c, 10)
            if(syns4):
                for z in syns4:
                    print("Adding alternative label %s" % z)
                    mylist.append(z)

            mylist = list(set(mylist))
            if(len(mylist) < 10):
                print("Searching in Altervista")
                syns5 = synonymsAltervista(c, ALTERVISTA_KEY)
                if(syns5):
                    for z in syns5:
                        print("Adding alternative label %s" % z)
                        mylist.append(z)

            mylist = list(set(mylist))
            if(len(mylist) < 10):
                print("Checking cosine distance...")
                list2 = checkCosineMatch(c,WIKTIONARY_FILE)
                mylist.extend(list2)

            mylist = list(set(mylist))
            if(len(mylist) < 10):
                print("Checking term with 2 lemmas...")
                list2 = checkLemmas(c,WIKTIONARY_FILE, 2)
                mylist.extend(list2)

            mylist = list(set(mylist))
            if(len(mylist) < 10):
                print("Checking term with 3 lemmas...")
                list2 = checkLemmas(c,WIKTIONARY_FILE, 3)
                mylist.extend(list2)

            mylist = list(set(mylist))
            if(len(mylist) < 10):
                print("Checking term with 6 lemmas...")
                list2 = checkLemmas(c,WIKTIONARY_FILE, 6)
                mylist.extend(list2)
        
            mylist = list(set(mylist))
            
            # removing elements containing the following characters
            test_str=" -'_"
            res = []
            for sub in mylist:
                flag = 0
                for ele in sub:
                    if ele in test_str:
                        flag = 1
                        print('Element %s will removed from the list' % (sub) )
                if not flag:
                    res.append(sub)

            mylist2 = []

            for element in res:
                kw_vector = dictionary.doc2bow(jieba.lcut(element))
                index = similarities.SparseMatrixSimilarity(tfidf[corpus], num_features = feature_cnt)
                sim = index[tfidf[kw_vector]]
                arr1 = np.array(sim)
                
                # https://thispointer.com/find-max-value-its-index-in-numpy-array-numpy-amax/
                maxSimilarity = np.amax(arr1)
                print('Element %s has Max similarity in internal market %s ' % (element, maxSimilarity))
                
                kw_vector2 = dictionary2.doc2bow(jieba.lcut(element))
                index2 = similarities.SparseMatrixSimilarity(tfidf[corpus2], num_features = feature_cnt2)
                sim2 = index2[tfidf[kw_vector2]]
                arr2 = np.array(sim2)
                maxSimilarity2 = np.amax(arr2)
                print('Element %s has Max similarity in digital single gateway %s ' % (element, maxSimilarity2))

                kw_vector3 = dictionary3.doc2bow(jieba.lcut(element))
                index3 = similarities.SparseMatrixSimilarity(tfidf[corpus3], num_features = feature_cnt3)
                sim3 = index3[tfidf[kw_vector3]]
                arr3 = np.array(sim3)
                maxSimilarity3 = np.amax(arr3)
                print('Element %s has Max similarity in gdpr %s ' % (element, maxSimilarity3))

                list_sim = [maxSimilarity, maxSimilarity2, maxSimilarity3]
                average = np.mean(list_sim)
                if(average > 0):
                    mylist2.append(element)
                #    result = np.where(arr1 == np.amax(arr1))
                #    print('Returned tuple of arrays :', result)
                #    print('List of Indices of maximum element :', result[0])
                #    print('text: ', texts[result[0][0].astype(int)])

            # result = np.where(arr1 == np.amax(arr1))
            #print('Returned tuple of arrays :', result)
            # print('List of Indices of maximum element :', result[0])
            #print('text: ', texts[result[0][0].astype(int)])

            for element in mylist2:
                labelURI = element.replace(" ","-").replace("(","-").replace(")","-").replace(",","-").replace("*","-").replace("&amp;","-").replace(".","-").replace("'","-")
                altLabelURI = URIRef("http://publications.europa.eu/resource/authority/publicservice-theme/label/" + labelURI)
                g.add((s, SKOSXL.altLabel, altLabelURI))
                g.add((altLabelURI, SKOSXL.literalForm, Literal(element, lang="en")))
g.serialize(destination=OUTPUT_FILE, format='turtle')
end = time.time()
timer(start, end)

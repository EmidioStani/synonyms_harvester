"""
.. module:: synonyms_harvester
   :platform: Unix, Windows
   :synopsis: A python script to enrich a skos list with synonyms taken from different sources
.. moduleauthor:: Emidio Stani <emidio.stani@pwc.com>
"""


import requests
from rdflib import Graph, Literal
from rdflib.namespace import RDF, SKOS
from rdflib import Namespace
import time
import simplejson
from SPARQLWrapper import SPARQLWrapper, JSON
from datamuse import datamuse
import re
import argparse


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
        }
        """)

    sparql.setReturnFormat(JSON)
    results = sparql.query().convert()
    resultslist = []
    for result in results["results"]["bindings"]:
        resultslist.append(result["altlabel"]["value"])

    return resultslist


def synonymsWordNet2(term):
    return synonymsFromSPARQLEndpoint("http://localhost:7200/repositories/wordnet-synonyms", term)


def synonymsUnesco(term):
    return synonymsFromSPARQLEndpoint("http://localhost:7200/repositories/unesco", term)


def synonymsDatamuse(term):
    api = datamuse.Datamuse()
    response = api.words(ml=term.lower(), max=10)
    # print(response)
    resultslist = []
    for i in response:
        if(i.get('tags') and ('syn' in i['tags'])):
            resultslist.append(i['word'])
    if(len(resultslist) == 0 and len(response) > 0):
        counter = 0
        maxwords = min(5, len(response))
        while(counter < maxwords):
            resultslist.append(response[counter]['word'])
            counter += 1
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
        print(response)
        syns = ''
        if 'error' not in response:
            for i in response['response']:
                # if i['list']['category'] == '(noun)':
                syns = syns + i['list']['synonyms'] + '|'
            arraylist = syns.split("|")
            arraylist = [re.sub(r'\(generic term\)', r'', a) for a in arraylist]
            arrayWithoutAntonyms = [x for x in arraylist if 'antonym' not in x]
    except requests.exceptions.RequestException as e:
        print(e)
    return arrayWithoutAntonyms


def timer(start, end):
    hours, rem = divmod(end-start, 3600)
    minutes, seconds = divmod(rem, 60)
    print("{:0>2}:{:0>2}:{:05.2f}".format(int(hours), int(minutes), seconds))

ALTERVISTA_KEY = 'xyz'
WIKTIONARY_FILE = 'syn_wiktionary.ttl'
INPUT_FILE = 'sample.rdf'
OUTPUT_FILE = 'output.ttl'
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
g = Graph()
g.parse(INPUT_FILE , format="xml")
for s, p, o in sorted(g.triples((None, RDF.type, SKOS.Concept))):
    for a, b, c in sorted(g.triples((s, SKOS.prefLabel, None))):
        print("%s has label %s" % (a, c))
        # syns = synonymsThesaurus(c.lower())
        # for synonym in syns:
        #    print(synonym.text)
        #    g.add( (a, SKOS.altLabel, Literal(synonym.text, lang="en")) )
        print("Searching in Wiktionary")
        syns2 = synonymsWiktionary(c, WIKTIONARY_FILE)
        if(syns2):
            for x, y, z in syns2:
                print("Adding alternative label %s" % z)
                g.add((a, SKOS.altLabel, Literal(z, lang="en")))
        print("Searching in Wordnet")
        syns3 = None
        syns3 = synonymsWordNet2(c)
        if(syns3):
            for z in syns3:
                print("Adding alternative label %s" % z)
                g.add((a, SKOS.altLabel, Literal(z, lang="en")))
        print("Searching in Unesco")
        syns6 = None
        syns6 = synonymsUnesco(c)
        if(syns6):
            for z in syns6:
                print("Adding alternative label %s" % z)
                g.add((a, SKOS.altLabel, Literal(z, lang="en")))
        if(not(syns2 or syns3 or syns6)):
            print("Searching in Datamuse")
            syns4 = synonymsDatamuse(c)
            if(len(syns4)) == 0:
                print("Searching in Altervista")
                syns5 = synonymsAltervista(c, ALTERVISTA_KEY)
                if(syns5):
                    for z in syns5:
                        print("Adding alternative label %s" % z)
                        g.add((a, SKOS.altLabel, Literal(z, lang="en")))
            else:
                for z in syns4:
                        print("Adding alternative label %s" % z)
                        g.add((a, SKOS.altLabel, Literal(z, lang="en")))
g.serialize(destination=OUTPUT_FILE, format='turtle')
end = time.time()
timer(start, end)

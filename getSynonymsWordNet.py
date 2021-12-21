import logging
import sys

from rdflib import Graph
from SPARQLWrapper import TURTLE, SPARQLWrapper


def query_to_file(endpoint, graph, output, format, limit=0, offset=0, ordered=False):
    logging.debug("Querying to file %s", output)
    sparql = SPARQLWrapper(endpoint)

    if graph:
        graph = "GRAPH <%s>" % graph
    else:
        graph = ""

    if limit:
        extra = "LIMIT %s OFFSET %s" % (limit, offset)
        if ordered:
            extra = "ORDER BY ?s ?p ?o " + extra
    else:
        extra = ""

    query = """
    PREFIX wordnet-onto: <http://wordnet-rdf.princeton.edu/ontology#>
    PREFIX ontolex: <http://www.w3.org/ns/lemon/ontolex#>
    PREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#>
    PREFIX skos: <http://www.w3.org/2004/02/skos/core#>
    CONSTRUCT {
      ?term rdf:type skos:Concept .
      ?term skos:prefLabel ?termlabel .
      ?term skos:altLabel ?synlabel .
    }
    WHERE {
      %s {
      ?noun rdf:type ontolex:LexicalConcept .
      ?noun wordnet-onto:partOfSpeech wordnet-onto:noun .
      ?term ontolex:isLexicalizedSenseOf ?noun .
      ?term2 ontolex:isLexicalizedSenseOf ?noun .
      FILTER(?term != ?term2) .
      BIND(strlang(strbefore(strafter(str(?term2),"lemma/"),"#"),"en") as  ?synlabel) .
      BIND(strlang(strbefore(strafter(str(?term),"lemma/"),"#"), "en") as  ?termlabel) .
      }
    } %s
  """ % (graph, extra)
    logging.debug("query: %s", query)
    sparql.setQuery(query)
    sparql.setReturnFormat(TURTLE)
    response = sparql.query().response

    if output == '-':
        out = sys.stdout
    else:
        out = open(output, "wb")

    size = 0
    while True:
        data = response.read(1024)
        size += len(data)
        if len(data) == 0:
            break
        out.write(data)
    out.close()
    logging.info("Wrote %d bytes to output file %s", size, output)
    return size 

query_to_file("http://localhost:7200/repositories/wordnet", "" , "syn_wordnet_2.ttl", "turtle", limit=500000, offset=1000)

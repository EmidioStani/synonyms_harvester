from SPARQLWrapper import SPARQLWrapper, TURTLE
from rdflib import Graph

sparql = SPARQLWrapper("http://localhost:7200/repositories/wordnet")
sparql.setQuery("""
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
      ?noun rdf:type ontolex:LexicalConcept .
      ?noun wordnet-onto:partOfSpeech wordnet-onto:noun .
      ?term ontolex:isLexicalizedSenseOf ?noun .
      ?term2 ontolex:isLexicalizedSenseOf ?noun .
      FILTER(?term != ?term2) .
      BIND(strlang(strbefore(strafter(str(?term2),"lemma/"),"#"),"en") as  ?synlabel) .
      BIND(strlang(strbefore(strafter(str(?term),"lemma/"),"#"), "en") as  ?termlabel) .
    }
""")

sparql.setReturnFormat(TURTLE)
results = sparql.query().convert()

g = Graph()
g.parse(data=results, format="turtle")
g.serialize(destination='syn_wordnet.ttl', format='turtle')

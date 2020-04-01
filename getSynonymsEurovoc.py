from SPARQLWrapper import SPARQLWrapper, TURTLE
from rdflib import Graph

sparql = SPARQLWrapper("http://localhost:7200/repositories/eurovoc")
sparql.setQuery("""
    PREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#>
    PREFIX skos: <http://www.w3.org/2004/02/skos/core#>
    PREFIX skos-xl: <http://www.w3.org/2008/05/skos-xl#>
    CONSTRUCT {
      ?term rdf:type skos:Concept .
      ?term skos:prefLabel ?form .
    }
    WHERE {
      ?term rdf:type skos:Concept .
      ?term skos-xl:prefLabel ?label .
      ?label skos-xl:literalForm ?form .
      FILTER(lang(?form)="en")
    }
""")

sparql.setReturnFormat(TURTLE)
results = sparql.query().convert()

g = Graph()
g.parse(data=results, format="turtle")
g.serialize(destination='syn_eurovoc.ttl', format='turtle')

import html2text
import nltk.data
from gensim import corpora, models, similarities
import jieba
import numpy as np

html = open("psi.html").read()
data = html2text.html2text(html)

tokenizer = nltk.data.load('tokenizers/punkt/english.pickle')

texts = tokenizer.tokenize(data)

texts2 = [jieba.lcut(text) for text in texts]
dictionary = corpora.Dictionary(texts2)
feature_cnt = len(dictionary.token2id)
corpus = [dictionary.doc2bow(text) for text in texts2]
tfidf = models.TfidfModel(corpus) 

keyword = 'Directive'
kw_vector = dictionary.doc2bow(jieba.lcut(keyword))
index = similarities.SparseMatrixSimilarity(tfidf[corpus], num_features = feature_cnt)
sim = index[tfidf[kw_vector]]

arr1 = np.array(sim)
maxElement = np.amax(arr1)
print('Max element from Numpy Array : ', maxElement)

result = np.where(arr1 == np.amax(arr1))
 
print('Returned tuple of arrays :', result)
print('List of Indices of maximum element :', result[0])

print('text: ', texts[result[0][0].astype(int)])
#arr = np.sort(arr1)[::-1]
 
#print('Sorted Array in Descending Order: ', arr)

#for i in range(len(sim)):
#    print('keyword is similar to text%d: %.2f' % (i + 1, sim[i]))
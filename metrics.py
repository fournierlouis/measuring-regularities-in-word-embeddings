import numpy as np
import sklearn

from sklearn.metrics.pairwise import cosine_similarity as cos_sim

from models import clean_pairs
from read_bats import bats_names_pairs

def token_embedding(tokenizer, model, word):
    tokenized_text = tokenizer.tokenize(word)
    indexed_tokens = tokenizer.convert_tokens_to_ids(tokenized_text)
    embeds = np.array([model[i] for i in indexed_tokens])
    embed = np.mean(embeds, axis=0)
    return(embed)

def permutation_onecycle(n):
    if type(n) == tuple:
        n1, n2 = n[0], n[1]
    else:
        n1, n2 = 0, n
    l=np.random.permutation(range(n1, n2))
    for i in range(n1, n2):
        if i==l[i-n1]:
            j=np.random.randint(n1, n2)
            while j==l[j-n1]:
                j=np.random.randint(n1, n2)
            l[i-n1], l[j-n1] = l[j-n1], l[i-n1]
    return(l)

def permutation_onecycle_avoidtrue(n, real): #May be a more optimal way
    test = False
    perm = permutation_onecycle(n)
    for i_r in range(len(real)):
        if real[i_r][1] == real[perm[i_r]][1]:
            test = True
    while test:
        test = False
        perm = permutation_onecycle(n)
        for i_r in range(len(real)):
            if real[i_r][1] == real[perm[i_r]][1]:
                test = True
    return(perm)

def shuffled_directions(model, idx_start, idx_end):
    perm_list = permutation_onecycle(len(idx_start))
    dirs = np.array([[model.wv.get_vector(idx_end[perm_list[i]]) - model.wv.get_vector(idx_start[i])
                                          for i in range(len(idx_start))]])
    return(dirs)

def similarite_offsets(list_offsets):
    sim_offsets = []
    for i in range(len(list_offsets)):
        sim_offsets.append([])
        list_tuples = list(list_offsets[i])
        for j in range(len(list_tuples)):
            for k in range(j+1,len(list_tuples)):
                sim_offsets[-1].append(cos_sim([list_tuples[j]], [list_tuples[k]])[0][0])
    return(np.array(sim_offsets))

def OCS_PCS(nb_perm, similarities, similarities_shuffle):
    ocs, pcs = [], []
    for i in range(len(similarities)):
        pcs_list = []
        for perm in range(nb_perm):
            y_true = [1 for j in range(len(similarities[i]))]+[0 for j in range(len(similarities_shuffle[perm][i]))]
            y_scores = list(similarities[i])+list(similarities_shuffle[perm][i])
            auc_temp = sklearn.metrics.roc_auc_score(y_true,y_scores)
            pcs_list.append(auc_temp)
        pcs.append(np.mean(pcs_list))
        ocs.append(np.mean(similarities[i]))
    return(ocs, pcs)

def word_embedding(model, word):
    if type(model) == list:
        # BERT or GPT-2
        model, tokenizer = model
        embedding = token_embedding(tokenizer, model, word)
    else:
        # gensim based model
        embedding = model.wv.get_vector(word)
    return(embedding)

def offsets(model, pairs_sets):
    return (np.array([[word_embedding(model, i[1]) - \
                       word_embedding(model, i[0])
                       for i in pairs_sets[k]]
                       for k in range(len(pairs_sets))]))

def shuffled_offsets(model, pairs_sets, nb_perms=50, avoid_true=True):
    shf_offsets = []
    for k in range(len(pairs_sets)):
        shf_offsets.append([])
        for perm in range(nb_perms):
            if avoid_true:
                perm_list = permutation_onecycle_avoidtrue(len(pairs_sets[k]), pairs_sets[k])
            else:
                perm_list = permutation_onecycle(len(pairs_sets[k]))
            offs = [word_embedding(model, pairs_sets[k][perm_list[i]][1]) - \
                    word_embedding(model, pairs_sets[k][i][0])
                    for i in range(len(pairs_sets[k]))]
            shf_offsets[-1].append(offs)
    return (shf_offsets)

def normal_and_shuffled_offsets(model, pairs_sets, nb_perms=50):
    pairs_sets = clean_pairs(model, pairs_sets)

    normal_offsets = offsets(model, pairs_sets)
    shf_offsets = shuffled_offsets(model, pairs_sets, nb_perms=nb_perms)

    return(normal_offsets, shf_offsets)


def metrics_from_model(model, nb_perms=50):
    names, pairs_sets = bats_names_pairs(dir="BATS_3.0")

    normal_offsets, shf_offsets = normal_and_shuffled_offsets(model, pairs_sets, nb_perms=nb_perms)

    similarities = similarite_offsets(normal_offsets)
    similarities_shuffle = [similarite_offsets(np.array(shf_offsets)[:, perm])
                            for perm in range(nb_perms)]

    ocs, pcs = OCS_PCS(nb_perms, similarities, similarities_shuffle)

    return (ocs, pcs)


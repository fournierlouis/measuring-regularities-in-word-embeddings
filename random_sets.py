import gensim
from gensim import utils
import gensim.downloader as api
from gensim.models.word2vec import Word2Vec, Word2VecKeyedVectors

import logging
import wget
from itertools import chain
import logging
from six import string_types
import numpy as np
import matplotlib.pyplot as plt
from sklearn.decomposition import PCA
import pickle
import os
import sklearn

import scipy
from scipy import sparse
from scipy.stats import ttest_ind
from scipy.sparse.linalg import norm
from scipy.stats import iqr

from sklearn.metrics import pairwise_distances
from sklearn.metrics.pairwise import cosine_distances
from sklearn.metrics.pairwise import euclidean_distances
from sklearn.metrics.pairwise import cosine_similarity as cos_sim
from sklearn.preprocessing import normalize
from sklearn.cluster import SpectralClustering

from svd2vec import svd2vec

import plotly.graph_objects as go
import plotly

import tensorflow
import transformers

from metrics import permutation_onecycle, similarite_offsets, normal_and_shuffled_offsets, OCS_PCS
from read_bats import vocab_bats, bats_names_pairs
from models import vocabulary_model


def offsets_perms_random(model, pairs_sets, vocabulary, nb_random=10, size_random_categ=50, limit_word=10000):
    vocabulary_list = list(vocabulary)
    vocab_used = vocab_bats(pairs_sets)

    # a* - a, a et a* de la même catégorie mais permuté
    perm_lists_permutation_within = []
    offsets_permutation_within = []
    for k_r in range(nb_random):
        perm_lists_permutation_within.append([])
        offsets_permutation_within.append([])
        for i in range(len(pairs_sets)):
            perm_list = permutation_onecycle(len(pairs_sets[i]))
            offsets_permutation_within[-1].append([])
            ds = list(pairs_sets[i])
            for k in range(len(ds)):
                di = ds[k]
                dj = ds[perm_list[k]]
                if di[0] in vocabulary and dj[1] in vocabulary and dj[1] != di[0]:
                    offsets_permutation_within[-1][-1].append(
                        model.wv.get_vector(dj[1]) - model.wv.get_vector(di[0]))
            perm_lists_permutation_within[-1].append(perm_list)

    offsets_mismatched_within = []
    perm_lists_mismatched_within = []
    for k_r in range(nb_random):
        perm_list_mismatched_within = np.hstack([permutation_onecycle(10),
                                                 permutation_onecycle((10, 20)),
                                                 permutation_onecycle((20, 30)),
                                                 permutation_onecycle((30, 40)),
                                                 ])
        perm_lists_mismatched_within.append(perm_list_mismatched_within)
        offsets_mismatched_within.append([])

        for i in range(len(pairs_sets)):
            offsets_mismatched_within[-1].append([])
            j = perm_list_mismatched_within[i]
            len_max = min(len(pairs_sets[i]), len(pairs_sets[j]))
            for k in range(len_max):
                di = list(pairs_sets[i])[k]
                dj = list(pairs_sets[j])[k]
                if dj[1] != di[0]:
                    offsets_mismatched_within[-1][-1].append(
                        model.wv.get_vector(dj[1]) - model.wv.get_vector(di[0]))

    # a* - a, a et a* de categories différentes, probablement très très grand pour bats!!
    offsets_mismatched_across = []
    perm_lists_mismatched_across = []
    for k_r in range(nb_random):
        perm_list_mismatched_across = permutation_onecycle(len(pairs_sets))
        perm_lists_mismatched_across.append(perm_list_mismatched_across)
        offsets_mismatched_across.append([])

        for i in range(len(pairs_sets)):
            offsets_mismatched_across[-1].append([])
            j = perm_list_mismatched_across[i]
            len_max = min(len(pairs_sets[i]), len(pairs_sets[j]))
            for k in range(len_max):
                di = list(pairs_sets[i])[k]
                dj = list(pairs_sets[j])[k]
                if dj[1] != di[0]:
                    offsets_mismatched_across[-1][-1].append(model.wv.get_vector(dj[1]) - model.wv.get_vector(di[0]))

    # For half random categories
    idx_random_categ = []
    for k_d in range(len(pairs_sets)):
        idx_random_categ.append([])
        for k in range(nb_random):
            rand_ints = np.random.choice(limit_word, size=len(pairs_sets[k_d]), replace=False)
            rand_vos = [vocabulary_list[r] for r in rand_ints if not vocabulary_list[r] in vocab_used]  # i?
            while len(rand_vos) < len(pairs_sets[k_d]):
                rand_int = int(np.random.choice(limit_word, size=1, replace=False))
                if not vocabulary_list[rand_int] in vocab_used and not vocabulary_list[rand_int] in rand_vos:
                    rand_vos.append(vocabulary_list[rand_int])
            idx_random_categ[-1].append(rand_vos)
    idx_random_categ = np.array(idx_random_categ)

    # a* - a, a d'un ensemble random
    offsets_random_start = np.array([[[model.wv.get_vector(pairs_sets[k_d][i][1]) - \
                                        model.wv.get_vector(idx_random_categ[k_d][k_r][i])
                                        for i in range(len(pairs_sets[k_d]))
                                        if pairs_sets[k_d][i][1] in vocabulary]
                                        for k_d in range(len(pairs_sets))] for k_r in range(nb_random)])

    # a* - a, a* d'un ensemble random
    offsets_random_end = np.array([[[model.wv.get_vector(idx_random_categ[k_d][k_r][i]) - \
                                        model.wv.get_vector(pairs_sets[k_d][i][0])
                                        for i in range(len(pairs_sets[k_d]))
                                        if pairs_sets[k_d][i][0] in vocabulary]
                                        for k_d in range(len(pairs_sets))] for k_r in range(nb_random)])

    # For random->random categories
    idx_random_full_start = [np.random.choice(limit_word, size=size_random_categ, replace=False) for k in range(nb_random)]
    idx_random_full_start = np.array(
        [[vocabulary_list[i] for i in idx_random_full_start[k] if not vocabulary_list[i] in vocab_used] for k in range(nb_random)])

    idx_random_full_end = []
    for k in range(nb_random):
        rand_ints = np.random.choice(limit_word, size=size_random_categ, replace=False)
        rand_vos = [vocabulary_list[r] for r in rand_ints if
                    not vocabulary_list[r] in vocab_used and not vocabulary_list[r] in idx_random_full_start[k]]
        while len(rand_vos) < 50:
            rand_int = int(np.random.choice(limit_word, size=1, replace=False))
            if not vocabulary_list[rand_int] in vocab_used and not vocabulary_list[rand_int] in rand_vos and not \
            vocabulary_list[rand_int] in idx_random_full_start[k]:
                rand_vos.append(vocabulary_list[rand_int])
        idx_random_full_end.append(rand_vos)
    idx_random_full_end = np.array(idx_random_full_end)

    # a* - a, a et a* d'ensembles random
    offsets_random_full = [
        np.array([[model.wv.get_vector(idx_random_full_end[k_r][i]) - model.wv.get_vector(idx_random_full_start[k_r][i])
                   for i in range(len(idx_random_full_start[k_r]))]
                  ]) for k_r in range(nb_random)]

    offsets_random = (offsets_permutation_within,
                      offsets_mismatched_within,
                      offsets_mismatched_across,
                      offsets_random_start,
                      offsets_random_end,
                      offsets_random_full)

    perm_lists = (perm_lists_permutation_within,
                  perm_lists_mismatched_within,
                  perm_lists_mismatched_across)

    idx_randoms = (idx_random_categ,
                   idx_random_full_start,
                   idx_random_full_end)

    return(offsets_random,
           perm_lists,
           idx_randoms)

def shuffled_offsets_random(model, pairs_sets, perm_lists, idx_randoms, nb_perms=50, nb_random=10):
    perm_lists_permutation_within, \
    perm_lists_mismatched_within, \
    perm_lists_mismatched_across = perm_lists

    idx_random_categ, \
    idx_random_full_start, \
    idx_random_full_end = idx_randoms

    # a* - a, a et a* de categories différentes, même grande catégorie pour bats probablement très très grand pour bats!!
    offsets_mismatched_within_shuffle = []
    for k_r in range(nb_random):
        offsets_mismatched_within_shuffle.append([])
        perm_list_intra = perm_lists_mismatched_within[k_r]
        for k in range(len(pairs_sets)):
            offsets_mismatched_within_shuffle[-1].append([])
            kj = perm_list_intra[k]
            len_max = min(len(pairs_sets[k]), len(pairs_sets[kj]))
            for perm in range(nb_perms):
                perm_list = permutation_onecycle(len_max)
                # perm_list = permutation_onecycle_avoidtrue(len_max, directions_tuples[kj])
                dirs = [model.wv.get_vector(pairs_sets[kj][perm_list[i]][1]) -
                        model.wv.get_vector(pairs_sets[k][i][0])
                        for i in range(len_max)]
                offsets_mismatched_within_shuffle[-1][-1].append(dirs)

    offsets_mismatched_across_shuffle = []
    for k_r in range(nb_random):
        offsets_mismatched_across_shuffle.append([])
        perm_list_across = perm_lists_mismatched_across[k_r]
        for k in range(len(pairs_sets)):
            offsets_mismatched_across_shuffle[-1].append([])
            kj = perm_list_across[k]
            len_max = min(len(pairs_sets[k]), len(pairs_sets[kj]))
            for perm in range(nb_perms):
                perm_list = permutation_onecycle(len_max)
                # perm_list = permutation_onecycle_avoidtrue(len_max, directions_tuples[kj])
                dirs = [model.wv.get_vector(pairs_sets[kj][perm_list[i]][1]) -
                        model.wv.get_vector(pairs_sets[k][i][0])
                        for i in range(len_max)]
                offsets_mismatched_across_shuffle[-1][-1].append(dirs)

    # a* - a, a d'un ensemble random, shuffle
    offsets_random_end_shuffle = []
    for k_r in range(nb_random):
        offsets_random_end_shuffle.append([])
        for k in range(len(pairs_sets)):
            offsets_random_end_shuffle[-1].append([])
            len_max = min(len(pairs_sets[k]), len(idx_random_categ[k][k_r]))
            for perm in range(nb_perms):
                perm_list = permutation_onecycle(len_max)
                dirs = [model.wv.get_vector(idx_random_categ[k][k_r][perm_list[i]]) -
                        model.wv.get_vector(pairs_sets[k][i][0])
                        for i in range(len_max)]
                offsets_random_end_shuffle[-1][-1].append(dirs)

    offsets_random_start_shuffle = []
    for k_r in range(nb_random):
        print(k_r)
        offsets_random_start_shuffle.append([])
        for k in range(len(pairs_sets)):
            offsets_random_start_shuffle[-1].append([])
            len_max = min(len(pairs_sets[k]), len(idx_random_categ[k][k_r]))
            for perm in range(nb_perms):
                perm_list = permutation_onecycle(len_max)
                dirs = [model.wv.get_vector(pairs_sets[k][perm_list[i]][1]) -
                        model.wv.get_vector(idx_random_categ[k][k_r][i])
                        for i in range(len_max)]
                offsets_random_start_shuffle[-1][-1].append(dirs)

############### A CHANGER PEUT ETRE
    offsets_random_full_shuffle = []
    for k_r in range(nb_random):
        print(k_r)
        offsets_random_full_shuffle.append([])
        offsets_random_full_shuffle[-1].append([])
        for perm in range(nb_perms):
            perm_list = permutation_onecycle(len(idx_random_full_start[k_r]))
            dirs = [model.wv.get_vector(idx_random_full_end[k_r][perm_list[i]]) -\
                    model.wv.get_vector(idx_random_full_start[k_r][i])
                    for i in range(len_max)]
            offsets_random_full_shuffle[-1][-1].append(dirs)

    #offsets_random_full_shuffle = [
    #    np.array([[model.wv.get_vector(idx_random_full_end[k_r][i]) - model.wv.get_vector(idx_random_full_start[k_r][i])
    #               for i in range(len(idx_random_full_start[k_r]))]
    #              ]) for k_r in range(nb_random)]

    #offsets_random_full_shuffle = [[shuffled_directions(model, idx_random[k_r], idx_random2[k_r])
    #                                         for perm in range(nb_perm)] #!!!!!!!!!!???????
    #                                        for k_r in range(nb_random)]

    offsets_random_shuffle = (offsets_mismatched_within_shuffle,
                      offsets_mismatched_across_shuffle,
                      offsets_random_start_shuffle,
                      offsets_random_end_shuffle,
                      offsets_random_full_shuffle)

    return(offsets_random_shuffle)


def similarities_random(offsets_random, pairs_sets, vocabulary, nb_random=10):
    offsets_permutation_within, \
    offsets_mismatched_within, \
    offsets_mismatched_across, \
    offsets_random_start, \
    offsets_random_end, \
    offsets_random_full = offsets_random

    similarities_permutation_within = [
        similarite_offsets(offsets_permutation_within[k_r]) for k_r in range(nb_random)]
    print("intra")
    similarities_mismatched_within = [
        similarite_offsets(offsets_mismatched_within[k_r]) for k_r in range(nb_random)]
    print("inter")
    similarities_mismatched_across = [similarite_offsets(offsets_mismatched_across[k_r]) for k_r
                                              in range(nb_random)]
    print("N -> R")
    similarities_random_start = [similarite_offsets(offsets_random_start[k_r])
                                                for k_r in range(nb_random)]
    print("R -> N")
    similarities_random_end = [similarite_offsets(offsets_random_end[k_r])
                                                for k_r in range(nb_random)]
    print("R R")
    similarities_random_full = [similarite_offsets(offsets_random_full[k_r]) for k_r in
                                                range(nb_random)]

    similarities_random = (similarities_permutation_within,
                           similarities_mismatched_within,
                           similarities_mismatched_across,
                           similarities_random_start,
                           similarities_random_end,
                           similarities_random_full)

    return(similarities_random)

def similarities_shuffle_random(offsets_random_shuffle, nb_random=10, nb_perms=50):
    offsets_mismatched_within_shuffle, \
    offsets_mismatched_across_shuffle, \
    offsets_random_start_shuffle, \
    offsets_random_end_shuffle, \
    offsets_random_full_shuffle = offsets_random_shuffle

    print('intra')
    similarities_mismatched_within_shuffle = [
        [similarite_offsets(np.array(offsets_mismatched_within_shuffle[k_r])[:, perm]) for
         perm in range(nb_perms)] for k_r in range(nb_random)]
    print('inter')
    similarities_mismatched_across_shuffle = [
        [similarite_offsets(np.array(offsets_mismatched_across_shuffle[k_r])[:, perm]) for perm in
         range(nb_perms)] for k_r in range(nb_random)]
    print('N>R')
    similarities_random_start_shuffle = [
        [similarite_offsets(np.array(offsets_random_start_shuffle[k_r])[:, perm]) for perm in
         range(nb_perms)] for k_r in range(nb_random)]
    print('R>N')
    similarities_random_end_shuffle = [
        [similarite_offsets(np.array(offsets_random_end_shuffle[k_r])[:, perm]) for perm in
         range(nb_perms)] for k_r in range(nb_random)]
    print('R>R')
    similarities_random_full_shuffle = [
        [similarite_offsets(offsets_random_full_shuffle[k_r][perm]) for perm in range(nb_perms)]
        for k_r in range(nb_random)]

    similarities_random_shuffle = (similarities_mismatched_within_shuffle,
                                   similarities_mismatched_across_shuffle,
                                   similarities_random_start_shuffle,
                                   similarities_random_end_shuffle,
                                   similarities_random_full_shuffle)

    return(similarities_random_shuffle)

def ocs_pcs_random(similarities, similarities_shuffle, similarities_random, similarities_random_shuffle, nb_random=10, nb_perms=50):
    similarities_permutation_within, \
    similarities_mismatched_within, \
    similarities_mismatched_across, \
    similarities_random_start, \
    similarities_random_end, \
    similarities_random_full = similarities_random

    similarities_mismatched_within_shuffle, \
    similarities_mismatched_across_shuffle, \
    similarities_random_start_shuffle, \
    similarities_random_end_shuffle, \
    similarities_random_full_shuffle = similarities_random_shuffle

    ocs, pcs = OCS_PCS(nb_perms,
                       similarities,
                       similarities_shuffle)

    metrics_tmp = np.array([OCS_PCS(nb_perms,
                                    similarities_permutation_within[k_r],
                                    similarities_shuffle) for k_r in range(nb_random)])
    ocs_permutation_within, pcs_permutation_within = metrics_tmp[:, 0], metrics_tmp[:, 1]

    metrics_tmp = np.array([OCS_PCS(nb_perms,
                                    similarities_mismatched_within[k_r],
                                    similarities_mismatched_within_shuffle[k_r]) for k_r in range(nb_random)])
    ocs_mismatched_within, pcs_mismatched_within = metrics_tmp[:, 0], metrics_tmp[:, 1]

    metrics_tmp = np.array([OCS_PCS(nb_perms,
                                    similarities_mismatched_across[k_r],
                                    similarities_mismatched_across_shuffle[k_r]) for k_r in range(nb_random)])
    ocs_mismatched_across, pcs_mismatched_across = metrics_tmp[:, 0], metrics_tmp[:, 1]

    metrics_tmp = np.array([OCS_PCS(nb_perms,
                                    similarities_random_start[k_r],
                                    similarities_random_start_shuffle[k_r]) for k_r in range(nb_random)])
    ocs_random_start, pcs_random_start = metrics_tmp[:, 0], metrics_tmp[:, 1]

    metrics_tmp = np.array([OCS_PCS(nb_perms,
                                    similarities_random_end[k_r],
                                    similarities_random_end_shuffle[k_r]) for k_r in range(nb_random)])
    ocs_random_end, pcs_random_end = metrics_tmp[:, 0], metrics_tmp[:, 1]

    metrics_tmp = np.array([OCS_PCS(nb_perms,
                                    similarities_random_full[k_r],
                                    similarities_random_full_shuffle[k_r]) for k_r in range(nb_random)])
    ocs_random_full, pcs_random_full = metrics_tmp[:, 0], metrics_tmp[:, 1]

    ocs_all = (ocs,
               ocs_permutation_within,
               ocs_mismatched_within,
               ocs_mismatched_across,
               ocs_random_start,
               ocs_random_end,
               ocs_random_full)

    pcs_all = (pcs,
               pcs_permutation_within,
               pcs_mismatched_within,
               pcs_mismatched_across,
               pcs_random_start,
               pcs_random_end,
               pcs_random_full)

    return(ocs_all, pcs_all)

def metrics_random_from_model(model, nb_perms=50, nb_random=50, size_random_categ=50, limit_word=10000):
    names, pairs_sets = bats_names_pairs(dir="BATS_3.0")
    vocabulary = vocabulary_model(model)

    normal_offsets, shf_offsets = normal_and_shuffled_offsets(model,
                                                              pairs_sets, nb_perms=nb_perms)

    offsets_random, \
    perm_lists, \
    idx_randoms = offsets_perms_random(model,
                                       pairs_sets,
                                       vocabulary,
                                       nb_random=nb_random, size_random_categ=size_random_categ, limit_word=limit_word)

    offsets_random_shuffle = shuffled_offsets_random(model,
                                                     pairs_sets,
                                                     perm_lists,
                                                     idx_randoms,
                                                     nb_perms=nb_perms, nb_random=nb_random)

    similarities = similarite_offsets(normal_offsets)
    similarities_shuffle = [similarite_offsets(np.array(shf_offsets)[:, perm])
                            for perm in range(nb_perms)]

    similarities_random_shuffle = similarities_shuffle_random(offsets_random_shuffle,
                                                              nb_random=nb_random, nb_perms=nb_perms)

    ocs_all, pcs_all = ocs_pcs_random(similarities,
                                      similarities_shuffle,
                                      similarities_random,
                                      similarities_random_shuffle,
                                      nb_random=nb_random, nb_perms=nb_perms)

    return (ocs_all, pcs_all)
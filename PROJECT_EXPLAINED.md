# The Project Explained From Scratch

No prior knowledge needed. Read this top to bottom once and you will understand the whole project.

**Project title:** Link Prediction in a Co-authorship Network: Recommending Future Research Collaborations
**Course:** Social Network Analysis (24AM7PESNA)

---

## 1. The project in one minute

Researchers write papers together. If you draw every researcher as a dot and connect two dots whenever those people have written a paper together, you get a network.

**Our question:** looking only at this network, can we guess which two researchers who have never worked together are likely to work together in the future?

**What we did:**
1. Took a real network of 5,242 physics researchers.
2. Hid 20% of the connections, as if they had not happened yet.
3. Used four simple formulas to guess which connections were hidden.
4. Checked how many guesses were right, to find the best formula.
5. Used the best formula to recommend 20 new collaborations.

**What we found:** the best formula is **Adamic-Adar**. On the standard test, it scored a real hidden connection above a fake one about 95.7% of the time, and it was the clear winner on a harder test (0.850, with the next best at 0.778). All of its top 100 guesses were real hidden connections, compared with about 5.3% if you picked at random from the same pool.

---

## 2. Basic ideas you need

### What is Social Network Analysis?
It is the study of relationships. Instead of asking "what is this person like?", it asks "who is this person connected to, and what does that pattern tell us?"

### Words used everywhere

| Term | Meaning | In our project |
|---|---|---|
| **Node** | A dot in the network | A researcher (author) |
| **Edge / link** | A line between two dots | The two authors wrote at least one paper together |
| **Neighbour** | A node directly connected to you | Your co-authors |
| **Degree** | Number of neighbours | How many co-authors you have |
| **Hub** | A node with a very high degree | An author with a huge number of co-authors |
| **Path length** | Steps needed to get from one node to another | "My co-author's co-author" is 2 steps away |

### What is link prediction?
It means guessing which missing links are likely to appear. LinkedIn's "People you may know" is the same kind of problem. We use it to recommend research partners.

### The main idea behind the project: triadic closure
If A works with B, and B works with C, then A and C are likely to end up working together too. Your friends' friends often become your friends. Three of our four formulas are built on this idea.

---

## 3. The dataset

We used **ca-GrQc** from SNAP, Stanford University's public collection of network datasets. It covers papers in the General Relativity and Quantum Cosmology category of arXiv from January 1993 to April 2003.

- Each author is only a number, such as `45`. Real names are not included.
- A paper with 10 authors connects all 10 to each other. This creates tightly connected groups.

### Cleaning the data
| Step | Count |
|---|---|
| Lines in the original file | 28,980 |
| Self-loops removed (an author linked to themself) | 12 lines |
| Duplicates removed (the file stores A-B and also B-A) | 14,484 lines |
| **Final network** | **5,242 authors, 14,484 links** |

### What the network looks like

The **largest connected component (LCC)** is the biggest group in which everyone can reach everyone else through some chain of co-authors. It holds 79% of the authors. All our prediction experiments use it.

| Measure | Full network | LCC | What it means |
|---|---|---|---|
| Authors | 5,242 | 4,158 | |
| Links | 14,484 | 13,422 | |
| Density | 0.00105 | 0.00155 | Only about 0.1% of all possible links exist, so the network is very sparse |
| Average degree | 5.53 | 6.46 | A typical author has about 5 or 6 co-authors |
| Average clustering | 0.530 | 0.557 | About half of the pairs of an author's co-authors have also worked together |
| Separate components | 355 | 1 | The full network is split into 355 separate groups |
| Diameter | - | 17 | The two most distant authors are 17 steps apart |
| Average path length | - | 6.05 | Any two authors are about 6 steps apart (a "small world") |

**Key point:** the network is sparse but highly clustered. Authors work in tight groups, and this is why our approach works.

Most authors have few co-authors (median 3), while a few have very many (maximum 81). This is called a **heavy-tailed** degree distribution.

### Important authors
We ranked authors in three ways. No author appears in all three top-10 lists, because each one measures something different.

| Measure | What it finds | Top author |
|---|---|---|
| **Degree** | The most co-authors | 21012 (81 co-authors) |
| **Betweenness** | "Bridges" that connect separate groups | 13801 |
| **PageRank** | Authors connected to other well-connected authors | 14265 |

### Communities
The **Louvain** algorithm finds groups that are densely connected inside. It found **42 communities** with a **modularity of 0.846**, which is very high (modularity measures how cleanly a network splits into groups). Also, 89% of the links we hid were between authors in the same community, so new collaborations mostly happen locally.

---

## 4. How we ran the experiment

Think of it as an exam for the formulas. We hide some answers, ask the formulas to find them, and mark the result.

### Step 1: Hide 20% of the links (train/test split)
- **Training graph:** 10,738 links that the formulas are allowed to see.
- **Test positives:** 2,684 hidden links they must find.

If we hid links completely at random, some authors could lose all their connections and become impossible to score. To prevent this, we first picked a **spanning tree**: 4,157 links that keep everyone connected. These always stay in the training graph, and hidden links are chosen only from the rest. The training graph therefore keeps all 4,158 authors and stays in one piece.

### Step 2: Add wrong answers (negative sampling)
A test with only correct answers proves nothing, since a formula that says "yes" to everything would score perfectly. So we added 2,684 **negatives**: random pairs of authors who are not linked anywhere in the network. That gives one wrong answer for each right answer (a 1:1 ratio).

We need to sample because the LCC has about 643 non-links for every real link, far too many to use them all in this test.

### Step 3: Prevent cheating (avoiding leakage)
**Leakage** means accidentally letting the answers into the exam. We prevented it in four ways:
1. Hidden links are removed before any score is calculated.
2. All scores are calculated on the training graph only.
3. Negatives are checked against the full network, so a hidden link can never be labelled as "wrong".
4. Any decision threshold is chosen using training data, never test data.

We also scored each training link with that link temporarily hidden, so it could not help predict itself.

### Step 4: Score every pair with four formulas

We wrote all four ourselves, then confirmed they match the NetworkX library exactly on 16,106 pairs (maximum difference: 0).

### Step 5: Mark the results
Using the metrics in Section 6.

### Step 6: Repeat
We repeated the split, sampling and scoring with 5 random seeds (42 to 46) to show the results were not just luck. A **seed** is a starting number for randomness. Using a fixed seed means anyone can reproduce the same results.

---

## 5. The four formulas, with an example

Here is an invented example. Priya and Rahul have never worked together.

- Priya's co-authors: Meena, Arjun, Kiran (degree 3)
- Rahul's co-authors: Meena, Arjun, Sita (degree 3)
- Shared co-authors: **Meena** (has only 3 co-authors) and **Arjun** (a hub with 60 co-authors)

| Formula | The idea | Calculation | Score |
|---|---|---|---|
| **Common Neighbours (CN)** | Count the shared co-authors | Meena + Arjun | **2** |
| **Jaccard** | Shared co-authors ÷ all their co-authors combined | 2 ÷ 4 (Meena, Arjun, Kiran, Sita) | **0.5** |
| **Adamic-Adar (AA)** | Count shared co-authors, but give less weight to hubs | 1/ln(3) + 1/ln(60) = 0.91 + 0.24 | **1.15** |
| **Preferential Attachment (PA)** | Multiply the two degrees | 3 × 3 | **9** |

### Why Adamic-Adar makes sense
Arjun works with 60 people, so sharing him says little: many people share Arjun. Meena works with only 3, so sharing her suggests that Priya and Rahul are in the same small team. In the example, Meena counts for 0.91 and Arjun for only 0.24.

### Weaknesses of each formula
- **CN:** treats a hub and a rare collaborator the same.
- **Jaccard:** can over-reward authors with very few co-authors. Two authors with identical small lists get a perfect 1.0.
- **AA:** gives 0 to any pair with no shared co-author.
- **PA:** only looks at popularity. Two famous authors in unrelated fields can score very highly.

---

## 6. How we measured success

| Metric | Plain meaning | Why we use it |
|---|---|---|
| **ROC-AUC** | Pick one real link and one fake link. How often does the real one score higher? 0.5 is random guessing and 1.0 is perfect | Judges the whole ranking |
| **Average Precision (AP)** | How well precision holds up as we try to find more of the real links | Summarises quality across the ranking |
| **Precision@K** | Of the top K guesses, how many are right? | This is what a user of a recommender actually sees |
| **Precision** | Of the pairs we said "yes" to, how many were real? | Shows how trustworthy a "yes" is |
| **Recall** | Of all real links, how many did we find? | Shows how many we missed |
| **F1** | A single score combining precision and recall | Balances the two |

**Threshold:** the score above which we say "yes, this will link". We chose the value that gave the best F1 on the training data, then used it unchanged on the test.

**ROC curve:** a graph of real links found against fake links wrongly accepted, as the threshold moves. **PR curve:** a graph of precision against recall. A better method hugs the top-left corner of the ROC graph and the top-right corner of the PR graph.

---

## 7. Results

### Main test (hidden links against random pairs)

| Method | ROC-AUC | AP | Precision | Recall | F1 |
|---|---|---|---|---|---|
| Common Neighbours | 0.9554 | 0.9550 | 0.995 | 0.912 | 0.952 |
| Jaccard | 0.9555 | 0.9555 | 0.995 | 0.912 | 0.952 |
| **Adamic-Adar** | **0.9557** | **0.9558** | 0.995 | 0.912 | 0.952 |
| Preferential Attachment | 0.8490 | 0.8662 | 0.652 | 0.902 | 0.756 |

**Why are the top three almost tied?** 99.6% of the random pairs share no co-author at all, while only 8.8% of the real hidden links share none. So simply asking "do they share anyone?" solves most of this test.

**Why are precision, recall and F1 identical for those three?** Their best thresholds all come down to the same rule: "at least one shared co-author".

**Precision@K was 1.0 for all four methods** at K = 10, 20, 50 and 100. The test was too easy to separate them at the top of the ranking, so we added two harder tests.

### Harder test 1: hard negatives
We kept the same hidden links, but replaced the fake pairs with 2,684 **hard negatives**: pairs who are not linked but already share a co-author. These are much harder to reject.

| Method | ROC-AUC | AP | Precision@10 |
|---|---|---|---|
| **Adamic-Adar** | **0.850** | **0.900** | 1.0 |
| Common Neighbours | 0.778 | 0.814 | 1.0 |
| Jaccard | 0.759 | 0.788 | 0.6 |
| Preferential Attachment | 0.644 | 0.681 | 1.0 |

This is where **Adamic-Adar clearly wins**, because weighting down hubs matters most when every pair shares someone.

### Harder test 2: hit rate
We ranked all 46,588 pairs in the training graph who share at least one co-author, then checked how many top guesses were really hidden links.

| Top K | Adamic-Adar | Common Neighbours | Jaccard | Pref. Attachment | Random pick |
|---|---|---|---|---|---|
| 10 | 1.00 | 1.00 | 1.00 | 1.00 | 0.053 |
| 100 | 1.00 | 1.00 | 0.44 | 0.92 | 0.053 |
| 500 | 0.986 | 0.984 | 0.16 | 0.54 | 0.053 |
| 1000 | 0.918 | 0.894 | 0.487 | 0.377 | 0.053 |

### Stability over 5 seeds

| Method | Mean ROC-AUC | Standard deviation |
|---|---|---|
| Adamic-Adar | 0.9568 | 0.0028 |
| Common Neighbours | 0.9564 | 0.0029 |
| Jaccard | 0.9564 | 0.0028 |
| Preferential Attachment | 0.8424 | 0.0043 |

The variation is tiny, so the results are reliable and not down to one lucky split.

---

## 8. The recommendations

Using Adamic-Adar on the whole LCC, we produced a Top-20 list of author pairs who have never worked together.

**Which pairs were considered?** Only the 63,288 unlinked pairs exactly 2 steps apart, meaning they share at least one co-author. Pairs further apart score 0 on CN, Jaccard and AA, so they could never reach the top of those lists.

**Number one recommendation:** authors **45 and 46**. They share **42 co-authors** and have an Adamic-Adar score of 10.598, yet they have no link in the data.

**What the Top-20 looks like:**
- Each pair shares 24 to 42 co-authors.
- Only 17 different authors appear, and they come from two very dense groups.
- Each pair and its shared co-authors form a group with a link density of 0.997 to 0.999, so nearly everyone in the group has worked with everyone else. This probably comes from very large multi-author papers or long-running collaborations.

**How the methods differ at number one:**

| Method | Top pair | Shared co-authors | Type of recommendation |
|---|---|---|---|
| Adamic-Adar and CN | 45 and 46 | 42 | A missing link inside a tight group |
| Jaccard | 19012 and 20305 | 5 | A small group with identical co-author lists |
| Preferential Attachment | 13801 and 21012 | 1 | Two popular authors who are not close |

---

## 9. Limitations (say these honestly)

1. **Not truly the future.** The dataset has no dates, so we hid links at random instead of training on older papers and testing on newer ones.
2. **The split makes the test slightly easier.** Hidden links come only from outside the spanning tree, and those links tend to be easier to predict. Results may be a little optimistic.
3. **Random negatives are easy.** They inflate the main scores, which is why we report the hard-negative results too.
4. **The 1:1 ratio is unrealistic.** The real ratio is about 643 non-links per link.
5. **CN, Jaccard and AA cannot reach far.** They give 0 to pairs 3 or more steps apart, so they cannot suggest collaborations between distant groups.
6. **We cannot verify the recommendations in the real world.** Authors are anonymous, and a "missing" link could be a data error.
7. **All links count equally.** One shared paper counts the same as twenty.

### How it could be improved
- **Katz index or Resource Allocation:** other scoring formulas. Katz also uses longer paths, so it can score more distant pairs.
- **Node2Vec or graph neural networks:** learn patterns from the network automatically.
- **A supervised classifier:** train a model to combine all four scores.
- **Dated data:** test on genuine future links.
- **Diverse recommendations:** stop one large group filling the whole list.

---

## 10. Visuals we made

All are in `visualizations/`.

| File | What it shows |
|---|---|
| `fig_degree_distribution` | Most authors have few co-authors, and a few have very many |
| `fig_network_overview` | The whole LCC, with bigger and darker dots for higher degree |
| `fig_communities` | The Louvain communities, with the eight largest coloured |
| `fig_roc_curves`, `fig_pr_curves` | How well each method ranks the pairs |
| `fig_metric_comparison` | Bar chart of the main scores |
| `fig_precision_at_k`, `fig_hit_rate` | Quality of the top guesses |
| `fig_seed_stability` | Results across the 5 seeds |
| `fig_recommendation_subgraph` | The Top-20, with predicted links as dashed red lines |
| `fig_recommendation_pairs` | Close-up of each method's top pair |
| `recommendation_subgraph_interactive.html` | The Top-20 network, which you can zoom and hover over in a browser |
| `cytoscape/` | Files for opening the network in Cytoscape, a network visualisation tool |

---

## 11. Where everything is

| Path | Contents |
|---|---|
| `notebook/link_prediction_ca_grqc.ipynb` | The full analysis, step by step |
| `src/data.py` | Loading, cleaning, statistics, split, negative sampling |
| `src/scores.py` | The four formulas |
| `src/evaluate.py` | The metrics |
| `src/recommend.py` | Top-K recommendations and hit rate |
| `src/viz.py` | All charts and network pictures |
| `dataset/` | The data files, plus a zip |
| `outputs/results.json` | Every number used in the report and slides |
| `outputs/top20_recommendations.csv`, `top10_recommendations.csv` | The recommendation lists |
| `report/report.pdf` | The report |
| `presentation/slides.pptx` | The slides |
| `presentation/script/` | Speaking scripts for each team member |
| `demo.py` | Scores any pair of authors live |
| `VIVA_NOTES.md` | Short answers to likely viva questions |

**To run everything again:** `.venv\Scripts\python build_all.py` (takes about 5 minutes).

**Tools used:** Python, NetworkX (networks), pandas and NumPy (data), scikit-learn (metrics), Matplotlib (charts), pyvis (interactive graph), ReportLab (report), python-pptx (slides).

---

## 12. If you only remember five things

1. **The task:** predict future research collaborations using only the network's structure.
2. **The data:** 5,242 authors and 14,484 links; we experiment on the largest connected part, 4,158 authors and 13,422 links.
3. **The method:** hide 20% of links, add an equal number of fake pairs, and score with four formulas on the visible links only.
4. **The result:** Adamic-Adar is best, with ROC-AUC 0.9568 ± 0.0028 and 0.850 on the harder test.
5. **The reason:** the network is highly clustered, so shared co-authors are a strong signal, and shared co-authors who are not hubs are the strongest signal of all.

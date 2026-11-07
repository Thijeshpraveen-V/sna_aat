# Presentation Script: Uday (Speaker 2)

**Slides:** 6 to 10 | **Time:** about 4 minutes | **Takes over from:** Thijesh | **Hands over to:** Sudarshan

Bold words are the ones to stress. Don't read word for word: learn the flow and look at the panel.

---

## Slide 6: Heuristic Formulas

Thank you, Thijesh. We compared four formulas. Each one gives a pair of authors a score, and a higher score means a link is more likely.

**Common Neighbours** simply counts the co-authors the two authors share. The idea is that people who share collaborators tend to become collaborators.

**Jaccard** divides that count by all their co-authors combined. This stops authors with very long lists from winning automatically.

**Adamic-Adar** also uses shared co-authors, but each one counts as **one over log of their degree**. A shared co-author who works with only 3 people counts for about 0.91, while one who works with 60 people counts for only about 0.24. A rare shared collaborator tells us much more than a hub who works with everyone.

**Preferential Attachment** just multiplies the two authors' degrees. It is a popularity score, and it ignores whether they are close in the network.

## Slide 7: Experimental Setup

To test these fairly, we hid **2,684 edges**, which is 20%, and kept **10,738** for training.

We then sampled the same number of **negatives**: pairs not linked anywhere in the full network. This means a hidden edge can never be mislabelled as a wrong answer.

To avoid leakage, **every score uses the training graph only**. The decision threshold is also chosen on training data, then applied unchanged to the test.

We measured ROC-AUC, Average Precision, Precision at K, and precision, recall and F1. We also repeated the split with **5 random seeds**, and added a harder test that I'll come to shortly.

## Slide 8: Results

Here are the results, with the best method highlighted.

Common Neighbours, Jaccard and Adamic-Adar are almost tied, with a ROC-AUC of about **0.955**. Preferential Attachment is well behind at **0.849**.

Why the near tie? **99.6%** of the random negatives share no co-author at all, but only **8.8%** of the real hidden links share none. So just asking "do they share anyone?" solves most of this test. That's also why these three have the same precision, recall and F1.

Across the 5 seeds, Adamic-Adar has the best mean, **0.9568, plus or minus 0.0028**. That variation is very small, so the results are stable.

## Slide 9: ROC and Precision-Recall Curves

These curves show the same story. The three local methods overlap almost completely, so you can barely tell them apart. Their ROC curve climbs straight up to about **0.91**, because about 91% of the hidden links share at least one co-author. The dotted line, Preferential Attachment, is clearly lower in both graphs. All four are well above the random line.

## Slide 10: Top-K Comparison

On the main test, Precision at K was **1.0 for all four methods**, so it couldn't separate them. So we ran two harder tests.

The first uses **hard negatives**: pairs that are not linked but already share a co-author. Look at the table. Adamic-Adar scores **0.850**, Common Neighbours **0.778**, Jaccard **0.759** and Preferential Attachment **0.644**. Jaccard's precision at 10 also falls to **0.6**. When every pair shares someone, down-weighting hubs really matters, and this is where Adamic-Adar clearly wins.

The second is **hit rate**. We ranked 46,588 candidate pairs and checked the top guesses. **100%** of Adamic-Adar's Top-100 were real hidden links, compared with about **5.3%** for a random pick.

**Handover:** So Adamic-Adar is our best method. Sudarshan will now show what it recommends.

---

## If you are asked

**What does a ROC-AUC of 0.95 mean?** If you take one real link and one fake pair, the method scores the real link higher about 95% of the time. Random guessing gives 0.5.

**Why are both ROC-AUC and Precision at K needed?** ROC-AUC judges the whole ranking, while Precision at K judges only the top, which is what a user actually sees.

**Why negative sampling?** The method needs wrong answers to reject, and there are about 643 non-links per link in the component, too many to use them all in this test.

**How was the threshold chosen?** We took the value that gave the best F1 on the training pairs, then kept it fixed for the test. For the three local methods, it comes down to "at least one shared co-author".

**Why is Preferential Attachment weaker?** It only looks at popularity, so it can't tell whether two authors work in the same group.

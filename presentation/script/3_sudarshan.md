# Presentation Script: Sudarshan (Speaker 3)

**Slides:** 11 to 16, plus the live demo | **Time:** about 3.5 minutes for slides, 2 to 3 minutes for the demo | **Takes over from:** Uday

Bold words are the ones to stress. Don't read word for word: learn the flow and look at the panel.

---

## Slide 11: Recommendations

Thank you, Uday. We then ran Adamic-Adar on the whole component to produce actual recommendations.

We considered **63,288 pairs** who are not linked but share at least one co-author. We removed self-pairs, existing links and duplicates.

The number one recommendation is authors **45 and 46**. They share **42 co-authors**, yet have no link in the data.

Each of the Top-20 pairs shares **24 to 42** co-authors. Their groups have a link density of about **0.997 or more**, meaning almost everyone in the group has already worked together. These look like missing links inside very large collaborations, which makes them strong suggestions.

## Slide 12: Visualization

On the left are the Louvain communities in the network. On the right are the top pairs from different methods. The **dashed red line** is the predicted link, and the light blue dots are shared co-authors.

You can see the difference clearly. Adamic-Adar picks pairs inside dense groups. Jaccard picks a small group with identical co-author lists. Preferential Attachment picks two big hubs that share just one co-author.

We also exported the network for Cytoscape, and built an interactive version that I'll show shortly.

## Slide 13: Insights

There are three main takeaways.

First, **collaboration is local**. **89%** of the hidden links fall inside a single community.

Second, **Adamic-Adar wins because it discounts hubs**, which is what matters on the harder test: 0.850 against 0.778 for Common Neighbours. Jaccard over-rewards tiny groups, and Preferential Attachment favours popular authors rather than close ones.

Third, the results are **stable**. The standard deviation over 5 splits is at most **0.0043** for every method.

## Slide 14: Limitations and Future Work

We should also be clear about the limitations. The dataset has **no dates**, so we simulated the future by hiding random links. Our split and our random negatives both make the test easier, and the 1:1 ratio is not realistic. Three of the formulas also can't reach pairs 3 or more steps apart. Finally, the authors are anonymous, so we can't check recommendations against real papers.

For future work, we could use the Katz index, Node2Vec embeddings or graph neural networks, train a classifier on these four scores, test on dated data, and make the recommendations more diverse.

## Slide 15: Conclusion

To conclude: we modelled a real co-authorship network, built a pipeline with no leakage, and compared four formulas. **Adamic-Adar performed best**, with a ROC-AUC of **0.9568** and **100%** of its Top-100 predictions being real hidden links. We also delivered explained recommendations, visualizations, a dataset package and a reproducible notebook.

**Before taking questions, here is a short demo.**

## Live demo (stay on slide 15, then switch to the terminal)

**Step 1: the terminal.** Type:

```powershell
.venv\Scripts\python demo.py 45 46
```

> This is the top pair for Adamic-Adar. They are not yet co-authors, they are 2 steps apart, and they share **42** co-authors. The Adamic-Adar score is **10.598**.

```powershell
.venv\Scripts\python demo.py 19012 20305
```

> This is Jaccard's top pair. Jaccard gives a perfect **1.0**, but they share only **5** co-authors, and both authors have exactly those 5.

```powershell
.venv\Scripts\python demo.py 13801 21012
```

> And this is the top pair for Preferential Attachment. The score is huge at **3,645**, but they share just **1** co-author. They are popular, not close. Same network, three very different answers.

**Step 2: the browser.** Open `visualizations/recommendation_subgraph_interactive.html`.

> This is the interactive Top-20. The blue dots are authors, and the **dashed red** lines are predicted collaborations. I can zoom in and hover over a link to see its score.

**Step 3: the notebook** (only if time allows). Scroll to the Top-20 table.

> Everything runs from this one notebook, and all our report and slide numbers come from its saved results.

## Slide 16: Thank You

Thank you for listening. We'd be happy to take your questions.

---

## If you are asked

**Are these recommendations correct?** We can't confirm them directly because the authors are anonymous. Our evidence is the hit-rate test: when we hid links, all of the Top-100 predictions turned out to be real hidden links.

**Why only pairs 2 steps apart?** Pairs further apart have no shared co-author, so they score 0 on Common Neighbours, Jaccard and Adamic-Adar and could never reach the top of those lists.

**Why do so few authors appear in the Top-20?** Only 17 different authors appear, because the highest scores come from two very dense groups. Making the list more diverse is part of our future work.

**What is a community?** A group of authors with many links inside the group and few outside it. Louvain finds these by maximising modularity.

**What is Cytoscape?** A desktop tool for visualising networks. We exported files so the network can be opened and styled there.

---

## Before the demo

- Open a terminal in the project folder (`sna_aat`) and run `demo.py` once beforehand. The first run took about 27 seconds in testing, and later runs should be quicker.
- Keep the browser page and notebook open in separate windows.
- If something fails, carry on with the figures on slide 12. Nothing in the demo needs internet.

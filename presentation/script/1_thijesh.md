# Presentation Script: Thijesh (Speaker 1)

**Slides:** 1 to 5 | **Time:** about 3.5 minutes | **Hands over to:** Uday

Bold words are the ones to stress. Don't read word for word: learn the flow and look at the panel.

---

## Slide 1: Title

Good morning. I'm Thijesh, and with me are Uday and Sudarshan. Our project for Social Network Analysis, under the guidance of Lavanya B Koppal, is **Link Prediction in a Co-authorship Network: Recommending Future Research Collaborations**.

In simple terms, we looked at who has written papers with whom, and used that to predict who might work together next.

## Slide 2: Agenda

I'll start with the problem, the dataset and our overall method. Uday will then explain the formulas, how we set up the experiment and our results. Sudarshan will finish with the recommendations, insights, limitations and a short live demo.

## Slide 3: Problem Definition

Research today is highly collaborative, but finding the right partner is hard. **Link prediction** treats this as a network problem. Each researcher is a **node**, and two researchers are joined by an **edge** if they have written at least one paper together.

So the question becomes: given today's network, which two unconnected authors are **most likely to collaborate in the future**?

This has real uses: collaborator suggestions on academic platforms, forming research teams, and suggesting reviewers for journals. It is similar to LinkedIn's "People you may know".

Formally, we hide some edges, score every unconnected pair using only the visible network, and check whether the hidden edges rank at the top.

## Slide 4: Dataset and Network

We used **ca-GrQc** from Stanford's SNAP collection. It covers arXiv papers in General Relativity and Quantum Cosmology from 1993 to 2003.

After removing 12 self-loops and 14,484 duplicate lines, we have **5,242 authors and 14,484 links**. Our experiments use the largest connected component, with **4,158 authors and 13,422 links**.

Two numbers matter most here. The density is only about **0.001**, so the network is very sparse. But the clustering coefficient is **0.53**, which is very high. So authors work in tight groups, and the co-authors of an author have often worked with each other.

Any two authors in the component are about **6 steps** apart, which is a small-world pattern. The graph on the right shows that most authors have few co-authors while a few have very many. Louvain also found **42 communities**, with a high modularity of **0.846**.

This clustering is the reason our approach works.

## Slide 5: Methodology

Here is our pipeline, from left to right.

We **load and clean** the data, and keep the **largest connected component**. We then **split the edges 80/20**. A spanning tree always stays in the training part, so the training graph stays connected and no author is cut off.

Next is **negative sampling**: we add an equal number of pairs that are not linked, so the formulas have wrong answers to reject.

The red box is the key step: we **score pairs on the training graph only**, using four formulas. This prevents leakage, meaning the hidden answers can't influence the scores. Finally, we **evaluate and recommend**.

We wrote all four formulas from scratch and checked them against the NetworkX library on 16,106 pairs. The maximum difference was **zero**.

**Handover:** Uday will now explain what these four formulas are and how they performed.

---

## If you are asked

**Why this dataset?** It is a public, well-known benchmark, the meaning of a link is clear, and its size lets us compute exact statistics on a laptop.

**What is the largest connected component?** The biggest group in which every author can reach every other author through a chain of co-authors. It holds 79% of the authors.

**Why a spanning tree?** Hiding edges at random could cut authors off, and then they couldn't be scored. A spanning tree contains every edge needed to keep the graph connected, so we only hide edges outside it.

**What does clustering of 0.53 mean?** On average, about half of the pairs of an author's co-authors have also worked with each other.

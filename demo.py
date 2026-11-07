"""Live viva demo: explain one recommendation.  Usage: python demo.py 45 46"""
import sys
sys.path.insert(0, "src")
import networkx as nx
from data import clean_edges, largest_cc, load_raw_edges
from scores import neighbour_sets, score_pairs

u, v = int(sys.argv[1]), int(sys.argv[2])
G, _, _ = clean_edges(load_raw_edges())
L = largest_cc(G)
nbrs = neighbour_sets(L)
s = score_pairs(L, [(u, v)], nbrs).iloc[0]
print(f"Authors {u} and {v}")
print(f"  Already co-authors?  {L.has_edge(u, v)}")
print(f"  Shortest path:       {nx.shortest_path_length(L, u, v)} hops")
print(f"  Degrees:             {len(nbrs[u])} and {len(nbrs[v])}")
print(f"  Common Neighbours:   {s.cn:.0f}")
print(f"  Jaccard:             {s.jaccard:.3f}")
print(f"  Adamic-Adar:         {s.adamic_adar:.3f}")
print(f"  Pref. Attachment:    {s.pref_attach:.0f}")

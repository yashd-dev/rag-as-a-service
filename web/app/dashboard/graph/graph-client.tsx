"use client";

import "@react-sigma/core/lib/style.css";

import { SigmaContainer, useRegisterEvents, useSetSettings, useSigma } from "@react-sigma/core";
import { NodeBorderProgram } from "@sigma/node-border";
import { createEdgeCurveProgram } from "@sigma/edge-curve";
import Graph from "graphology";
import MiniSearch from "minisearch";
import { RefreshCw, Search, ZoomIn, ZoomOut } from "lucide-react";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import type { MouseEvent as ReactMouseEvent } from "react";
import type { Settings as SigmaSettings } from "sigma/settings";
import { EdgeRectangleProgram, NodeCircleProgram } from "sigma/rendering";

import { Button } from "@/components/ui/button";
import type { Project, ProjectGraph } from "@/lib/backend";

type Selection =
  | { type: "node"; id: string; label: string; degree: number; neighbors: string[] }
  | { type: "edge"; id: string; label: string; source: string; target: string }
  | null;

type GraphClientProps = {
  project: Project;
  initialStatus: { node_count: number; edge_count: number } | null;
};

const palette = ["#38bdf8", "#34d399", "#f59e0b", "#f472b6", "#a78bfa", "#fb7185", "#22d3ee", "#84cc16"];

function positionFromId(id: string) {
  let hash = 0;
  for (let i = 0; i < id.length; i += 1) hash = Math.imul(31, hash) + id.charCodeAt(i);
  return {
    x: ((hash & 0xffff) / 0xffff - 0.5) * 20,
    y: (((hash >>> 16) & 0xffff) / 0xffff - 0.5) * 20,
  };
}

function buildSigmaGraph(data: ProjectGraph) {
  const graph = new Graph({ multi: true, type: "directed" });
  const degree = new Map<string, number>();
  const incoming = new Map<string, number>();
  const outgoing = new Map<string, string[]>();
  data.edges.forEach((edge) => {
    degree.set(edge.source, (degree.get(edge.source) || 0) + 1);
    degree.set(edge.target, (degree.get(edge.target) || 0) + 1);
    incoming.set(edge.target, (incoming.get(edge.target) || 0) + 1);
    outgoing.set(edge.source, [...(outgoing.get(edge.source) || []), edge.target]);
  });
  const roots = data.nodes.map((node) => node.id).filter((id) => !incoming.has(id));
  const queue = roots.length ? [...roots] : data.nodes.slice(0, 1).map((node) => node.id);
  const level = new Map<string, number>(queue.map((id) => [id, 0]));
  for (let index = 0; index < queue.length; index += 1) {
    const source = queue[index];
    for (const target of outgoing.get(source) || []) {
      const nextLevel = (level.get(source) || 0) + 1;
      if (!level.has(target) || nextLevel > (level.get(target) || 0)) {
        level.set(target, nextLevel);
        queue.push(target);
      }
    }
  }
  const rowsByLevel = new Map<number, string[]>();
  data.nodes.forEach((node) => {
    const nodeLevel = level.get(node.id) ?? rowsByLevel.size;
    rowsByLevel.set(nodeLevel, [...(rowsByLevel.get(nodeLevel) || []), node.id]);
  });
  const positions = new Map<string, { x: number; y: number }>();
  rowsByLevel.forEach((ids, nodeLevel) => {
    ids.forEach((id, row) => {
      positions.set(id, { x: nodeLevel * 8, y: (row - (ids.length - 1) / 2) * 3 });
    });
  });
  data.nodes.forEach((node, index) => {
    const pos = positions.get(node.id) || positionFromId(node.id);
    graph.addNode(node.id, {
      ...pos,
      label: node.label || node.id,
      size: Math.min(18, 5 + Math.sqrt(degree.get(node.id) || 1) * 3),
      color: palette[index % palette.length],
      borderColor: "#ffffff",
    });
  });
  data.edges.forEach((edge, index) => {
    if (!graph.hasNode(edge.source) || !graph.hasNode(edge.target)) return;
    graph.addDirectedEdgeWithKey(`${edge.source}->${edge.target}:${edge.label || "related"}:${index}`, edge.source, edge.target, {
      label: edge.label || "related",
      size: 1.4,
      color: "rgba(148, 163, 184, 0.58)",
    });
  });
  return graph;
}

const sigmaSettings: Partial<SigmaSettings> = {
  allowInvalidContainer: true,
  defaultNodeType: "border",
  defaultEdgeType: "rect",
  nodeProgramClasses: { border: NodeBorderProgram, circle: NodeCircleProgram },
  edgeProgramClasses: { rect: EdgeRectangleProgram, curved: createEdgeCurveProgram() },
  enableEdgeEvents: true,
  renderEdgeLabels: true,
  labelRenderedSizeThreshold: 8,
  labelSize: 12,
  edgeLabelSize: 9,
  labelColor: { color: "#111827" },
  edgeLabelColor: { color: "#374151" },
  defaultEdgeColor: "#64748b",
  hideEdgesOnMove: false,
};

function SigmaGraph({ graph, focusedNode, selectedNode, onSelect }: { graph: Graph; focusedNode: string | null; selectedNode: string | null; onSelect: (selection: Selection) => void }) {
  const sigma = useSigma();
  const registerEvents = useRegisterEvents();
  const setSettings = useSetSettings();
  const [draggedNode, setDraggedNode] = useState<string | null>(null);

  useEffect(() => {
    sigma.setGraph(graph);
    setSettings({ defaultEdgeType: "rect" });
    window.setTimeout(() => sigma.getCamera().animatedReset({ duration: 350 }), 0);
    return undefined;
  }, [graph, setSettings, sigma]);

  useEffect(() => {
    registerEvents({
      downNode: (event) => {
        setDraggedNode(event.node);
        graph.setNodeAttribute(event.node, "highlighted", true);
      },
      mousemovebody: (event) => {
        if (!draggedNode) return;
        const pos = sigma.viewportToGraph(event);
        graph.setNodeAttribute(draggedNode, "x", pos.x);
        graph.setNodeAttribute(draggedNode, "y", pos.y);
        event.preventSigmaDefault();
        event.original.preventDefault();
        event.original.stopPropagation();
      },
      mouseup: () => {
        if (!draggedNode) return;
        graph.removeNodeAttribute(draggedNode, "highlighted");
        setDraggedNode(null);
      },
      clickNode: (event) => {
        const neighbors = graph.neighbors(event.node).map((id) => graph.getNodeAttribute(id, "label") as string);
        onSelect({ type: "node", id: event.node, label: graph.getNodeAttribute(event.node, "label") as string, degree: graph.degree(event.node), neighbors });
      },
      clickEdge: (event) => {
        const [source, target] = graph.extremities(event.edge);
        onSelect({ type: "edge", id: event.edge, label: graph.getEdgeAttribute(event.edge, "label") as string, source: graph.getNodeAttribute(source, "label") as string, target: graph.getNodeAttribute(target, "label") as string });
      },
      clickStage: () => onSelect(null),
    });
  }, [draggedNode, graph, onSelect, registerEvents, sigma]);

  useEffect(() => {
    const selected = selectedNode || focusedNode;
    setSettings({
      nodeReducer: (node, data) => {
        const active = selected && (node === selected || graph.areNeighbors(node, selected));
        return selected && !active ? { ...data, color: "rgba(100, 116, 139, 0.28)", label: "" } : data;
      },
      edgeReducer: (edge, data) => {
        if (!selected) return data;
        const [source, target] = graph.extremities(edge);
        return source === selected || target === selected ? { ...data, color: "#2563eb", size: 2.5 } : { ...data, hidden: true };
      },
    });
  }, [focusedNode, graph, selectedNode, setSettings]);

  return null;
}

export function GraphClient({ project, initialStatus }: GraphClientProps) {
  const [data, setData] = useState<ProjectGraph | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [query, setQuery] = useState("");
  const [focusedNode, setFocusedNode] = useState<string | null>(null);
  const [selectedNode, setSelectedNode] = useState<string | null>(null);
  const [selection, setSelection] = useState<Selection>(null);
  const cameraRef = useRef<ReturnType<typeof useSigma> | null>(null);

  const load = useCallback(async () => {
    setIsLoading(true);
    setError(null);
    try {
      const response = await fetch(`/dashboard/graph/${project.id}/data`, { cache: "no-store" });
      if (!response.ok) throw new Error(await response.text());
      setData((await response.json()) as ProjectGraph);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not load graph");
    } finally {
      setIsLoading(false);
    }
  }, [project.id]);

  useEffect(() => {
    const timer = window.setTimeout(() => void load(), 0);
    return () => window.clearTimeout(timer);
  }, [load]);

  const graph = useMemo(() => (data ? buildSigmaGraph(data) : null), [data]);
  const search = useMemo(() => {
    if (!data) return null;
    const engine = new MiniSearch<{ id: string; label: string }>({ fields: ["label"], idField: "id", searchOptions: { prefix: true, fuzzy: 0.2 } });
    engine.addAll(data.nodes.map((node) => ({ id: node.id, label: node.label || node.id })));
    return engine;
  }, [data]);
  const results = useMemo(() => {
    if (!query.trim() || !search) return [];
    return search.search(query).slice(0, 8);
  }, [query, search]);
  const counts = { nodes: data?.nodes.length ?? initialStatus?.node_count ?? 0, edges: data?.edges.length ?? initialStatus?.edge_count ?? 0 };

  const chooseNode = (id: string) => {
    if (!graph) return;
    setFocusedNode(null);
    setSelectedNode(id);
    const neighbors = graph.neighbors(id).map((neighbor) => graph.getNodeAttribute(neighbor, "label") as string);
    setSelection({ type: "node", id, label: graph.getNodeAttribute(id, "label") as string, degree: graph.degree(id), neighbors });
  };

  return (
    <div className="flex min-h-[calc(100svh-4rem)] flex-col bg-background">
      <div className="flex h-16 items-center justify-between border-b px-4 md:px-6">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight">Graph</h1>
          <p className="text-sm text-muted-foreground">LightRAG-style interactive Neo4j entity graph.</p>
        </div>
        <Button variant="outline" className="h-9 px-3 font-normal" onClick={() => void load()} disabled={isLoading}>
          <RefreshCw className={isLoading ? "animate-spin" : ""} /> Refresh
        </Button>
      </div>

      <div className="grid flex-1 gap-4 p-4 md:grid-cols-[320px_1fr] md:p-6">
        <aside className="flex min-h-0 flex-col rounded-xl border bg-card p-4">
          <p className="text-xs uppercase tracking-wide text-muted-foreground">Corpus</p>
          <h2 className="mt-2 font-medium tracking-tight">{project.name}</h2>
          <div className="mt-5 grid grid-cols-2 gap-3 text-sm">
            <div className="rounded-lg bg-background p-3"><p className="text-muted-foreground">Nodes</p><p className="mt-1 text-2xl font-semibold">{counts.nodes}</p></div>
            <div className="rounded-lg bg-background p-3"><p className="text-muted-foreground">Edges</p><p className="mt-1 text-2xl font-semibold">{counts.edges}</p></div>
          </div>
          <label className="mt-5 flex items-center gap-2 rounded-lg border bg-background px-3 py-2 text-sm">
            <Search className="size-4 text-muted-foreground" />
            <input className="min-w-0 flex-1 bg-transparent outline-none" placeholder="Search nodes" value={query} onChange={(event) => setQuery(event.target.value)} />
          </label>
          {results.length ? (
            <div className="mt-2 max-h-52 overflow-auto rounded-lg border bg-background p-1">
              {results.map((result) => (
                <button key={result.id} className="block w-full rounded-md px-3 py-2 text-left text-sm hover:bg-muted" onMouseEnter={() => setFocusedNode(result.id)} onClick={() => chooseNode(result.id)}>
                  {result.label}
                </button>
              ))}
            </div>
          ) : null}
          <div className="mt-5 rounded-lg border bg-background p-3 text-sm">
            {selection?.type === "node" ? (
              <>
                <p className="font-medium">{selection.label}</p>
                <p className="mt-1 text-muted-foreground">{selection.degree} relationships</p>
                <div className="mt-3 flex flex-wrap gap-1.5">
                  {selection.neighbors.slice(0, 18).map((neighbor) => <span key={neighbor} className="rounded-full bg-primary/10 px-2 py-1 text-xs text-primary">{neighbor}</span>)}
                </div>
              </>
            ) : selection?.type === "edge" ? (
              <>
                <p className="font-medium">{selection.label}</p>
                <p className="mt-1 text-muted-foreground">{selection.source} {"->"} {selection.target}</p>
              </>
            ) : (
              <p className="text-muted-foreground">Click nodes or edges to inspect properties. Drag nodes, pan canvas, zoom, and search like LightRAG.</p>
            )}
          </div>
        </aside>

        <div className="relative min-h-[720px] overflow-hidden rounded-xl border bg-white">
          {error ? <div className="grid h-full place-items-center p-6 text-center text-sm text-destructive">{error}</div> : null}
          {!error && isLoading ? <div className="grid h-full place-items-center text-sm text-muted-foreground">Loading graph...</div> : null}
          {!error && !isLoading && graph && graph.order > 0 ? (
            <SigmaContainer settings={sigmaSettings} className="h-full w-full bg-white">
              <SigmaGraph graph={graph} focusedNode={focusedNode} selectedNode={selectedNode} onSelect={(value) => { setSelection(value); setSelectedNode(value?.type === "node" ? value.id : null); }} />
              <CameraControls cameraRef={cameraRef} />
            </SigmaContainer>
          ) : null}
          {!error && !isLoading && graph && graph.order === 0 ? <div className="grid h-full place-items-center p-6 text-center text-sm text-muted-foreground">No entities extracted yet.</div> : null}
          <div className="absolute right-4 top-4 flex gap-2">
            <CanvasButton onClick={() => cameraRef.current?.getCamera().animatedZoom({ duration: 250 })}><ZoomIn className="size-4" /></CanvasButton>
            <CanvasButton onClick={() => cameraRef.current?.getCamera().animatedUnzoom({ duration: 250 })}><ZoomOut className="size-4" /></CanvasButton>
            <CanvasButton onClick={() => cameraRef.current?.getCamera().animatedReset({ duration: 350 })}>Fit</CanvasButton>
          </div>
        </div>
      </div>
    </div>
  );
}

function CameraControls({ cameraRef }: { cameraRef: React.MutableRefObject<ReturnType<typeof useSigma> | null> }) {
  const sigma = useSigma();
  useEffect(() => {
    cameraRef.current = sigma;
    return () => {
      cameraRef.current = null;
    };
  }, [cameraRef, sigma]);
  return null;
}

function CanvasButton({ children, onClick }: { children: React.ReactNode; onClick: (event: ReactMouseEvent<HTMLButtonElement>) => void }) {
  return <button className="rounded-lg border border-white/10 bg-black/55 px-3 py-2 text-sm text-white shadow-lg backdrop-blur hover:bg-black/75" onClick={onClick}>{children}</button>;
}

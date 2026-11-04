<template>
  <div class="workflow-canvas" :aria-label="`${label} workflow`">
    <div class="workflow-toolbar">
      <span
        >{{ label }}
        <small
          >{{ graph.nodes.length }} bubbles · {{ graph.edges.length }} connections</small
        ></span
      >
      <div>
        <button type="button" aria-label="Zoom out" @click="zoom = Math.max(0.35, zoom - 0.15)">
          −
        </button>
        <button type="button" @click="zoom = 1">{{ Math.round(zoom * 100) }}%</button>
        <button type="button" aria-label="Zoom in" @click="zoom = Math.min(1.75, zoom + 0.15)">
          +
        </button>
        <button type="button" @click="fit">Fit</button>
        <button v-if="editable" type="button" @click="$emit('arrange')">Auto arrange</button>
      </div>
    </div>
    <div
      ref="viewport"
      class="workflow-viewport"
      @pointerdown="startPan"
      @pointermove="move"
      @pointerup="finish"
      @pointercancel="cancel"
    >
      <div :style="{ width: `${width * zoom}px`, height: `${height * zoom}px` }">
        <div
          class="workflow-sheet"
          :style="{ width: `${width}px`, height: `${height}px`, transform: `scale(${zoom})` }"
        >
          <div
            v-for="(lane, index) in graph.lanes"
            :key="index"
            class="workflow-lane"
            :style="{ left: `${28 + index * 310}px` }"
          >
            {{ lane }}
          </div>
          <svg
            class="workflow-connectors"
            :width="width"
            :height="height"
            aria-label="Workflow connections"
          >
            <defs>
              <marker
                :id="arrowId"
                viewBox="0 0 10 10"
                refX="9"
                refY="5"
                markerWidth="7"
                markerHeight="7"
                orient="auto-start-reverse"
              >
                <path d="M 0 0 L 10 5 L 0 10 z" fill="#64748b" />
              </marker>
            </defs>
            <g v-for="(edge, index) in graph.edges" :key="`${edge.from}-${edge.to}-${index}`">
              <path
                :d="edgePath(edge)"
                fill="none"
                stroke="#64748b"
                stroke-width="2"
                :stroke-dasharray="edge.suggested ? '6 4' : undefined"
                :marker-end="`url(#${arrowId})`"
              />
              <title>{{ edge.from }} → {{ edge.to }} · {{ edge.label }}</title>
            </g>
          </svg>
          <button
            v-for="node in graph.nodes"
            :key="node.id"
            type="button"
            :class="[
              'workflow-node',
              `node-${node.kind.toLowerCase().replaceAll(' ', '-')}`,
              { selected: selectedId === node.id, rejected: node.status === 'Not supported' },
            ]"
            :style="{
              left: `${position(node).x}px`,
              top: `${position(node).y}px`,
              width: `${nodeWidth}px`,
              height: `${nodeHeight}px`,
            }"
            :aria-pressed="selectedId === node.id"
            :aria-label="`${node.title}: ${node.description || 'New entry'}`"
            @pointerdown.stop="startNode($event, node)"
            @click="select(node)"
          >
            <span class="workflow-node-kind">{{ node.title }}</span>
            <span class="workflow-node-description">{{
              node.description || 'Select to describe this finding or event'
            }}</span>
            <span class="workflow-node-meta"
              >{{
                node.id === 'incident'
                  ? node.row.event_datetime || 'Incident overview'
                  : node.id
              }}<span v-if="node.status"> · {{ node.status }}</span></span
            >
            <span v-if="node.evidence.length" class="workflow-node-evidence"
              >{{ node.evidence.length }} evidence reference{{
                node.evidence.length === 1 ? '' : 's'
              }}</span
            >
          </button>
        </div>
      </div>
    </div>
    <p class="workflow-caption">
      Select a bubble to view or edit it.
      {{ editable ? 'Drag bubbles to arrange them. ' : '' }}Scroll or drag the background to
      explore. Dashed connectors show
      {{ mode === 'timeline' ? 'time sequence' : 'unconfirmed findings' }}.
    </p>
  </div>
</template>
<script setup>
import { computed, ref, useId } from 'vue'
import { nodeHeight, nodeWidth } from '../workflow'
const props = defineProps({
  graph: { type: Object, required: true },
  label: String,
  mode: String,
  selectedId: String,
  editable: Boolean,
})
const emit = defineEmits(['select', 'move', 'arrange'])
const viewport = ref(null),
  zoom = ref(1),
  drag = ref(null)
const arrowId = `workflow-arrow-${useId().replaceAll(':', '')}`
let suppressClick = false
const position = (node) => (drag.value?.id === node.id ? drag.value : node)
const width = computed(() =>
  Math.max(700, ...props.graph.nodes.map((node) => position(node).x + nodeWidth + 45)),
)
const height = computed(() =>
  Math.max(370, ...props.graph.nodes.map((node) => position(node).y + nodeHeight + 45)),
)
function edgePath(edge) {
  const a = position(props.graph.nodes.find((node) => node.id === edge.from)),
    b = position(props.graph.nodes.find((node) => node.id === edge.to))
  const right = b.x >= a.x,
    ax = a.x + (right ? nodeWidth : 0),
    bx = b.x + (right ? 0 : nodeWidth),
    ay = a.y + nodeHeight / 2,
    by = b.y + nodeHeight / 2
  if (Math.abs(a.x - b.x) < nodeWidth) {
    const x = Math.max(a.x, b.x) + nodeWidth + 22
    return `M ${a.x + nodeWidth} ${ay} C ${x} ${ay}, ${x} ${by}, ${b.x + nodeWidth} ${by}`
  }
  if (Math.abs(a.x - b.x) > nodeWidth + 110) {
    // Route past intervening lanes instead of running behind another bubble,
    // which could suggest a causal connection that was never recorded.
    const direction = right ? 1 : -1
    const exit = ax + direction * 20,
      entry = bx - direction * 20
    const track =
      Math.max(a.y, b.y) + nodeHeight + 20 + (props.graph.edges.indexOf(edge) % 3) * 8
    return `M ${ax} ${ay} L ${exit} ${ay} L ${exit} ${track} L ${entry} ${track} L ${entry} ${by} L ${bx} ${by}`
  }
  return `M ${ax} ${ay} C ${(ax + bx) / 2} ${ay}, ${(ax + bx) / 2} ${by}, ${bx} ${by}`
}
function startNode(event, node) {
  suppressClick = false
  if (!props.editable || !node.table || event.button !== 0) return
  drag.value = {
    id: node.id,
    x: node.x,
    y: node.y,
    originalX: node.x,
    originalY: node.y,
    startX: event.clientX,
    startY: event.clientY,
  }
  viewport.value.setPointerCapture(event.pointerId)
}
function startPan(event) {
  if (event.button !== 0) return
  suppressClick = false
  drag.value = {
    pan: true,
    startX: event.clientX,
    startY: event.clientY,
    scrollX: viewport.value.scrollLeft,
    scrollY: viewport.value.scrollTop,
  }
  viewport.value.setPointerCapture(event.pointerId)
}
function move(event) {
  const d = drag.value
  if (!d) return
  if (d.pan) {
    viewport.value.scrollLeft = d.scrollX - event.clientX + d.startX
    viewport.value.scrollTop = d.scrollY - event.clientY + d.startY
  } else {
    d.x = Math.min(20000, Math.max(16, d.originalX + (event.clientX - d.startX) / zoom.value))
    d.y = Math.min(20000, Math.max(48, d.originalY + (event.clientY - d.startY) / zoom.value))
    if (Math.abs(event.clientX - d.startX) + Math.abs(event.clientY - d.startY) > 5)
      suppressClick = true
  }
}
function cancel() {
  drag.value = null
  suppressClick = false
}
function finish() {
  const d = drag.value
  if (d && !d.pan && suppressClick)
    emit('move', { id: d.id, x: Math.round(d.x), y: Math.round(d.y) })
  drag.value = null
}
function select(node) {
  if (suppressClick) {
    suppressClick = false
    return
  }
  emit('select', node.id)
}
function fit() {
  zoom.value = Math.min(1, Math.max(0.35, (viewport.value?.clientWidth || 900) / width.value))
}
</script>
<style scoped>
.workflow-canvas {
  border: 1px solid #dce3ec;
  border-radius: 12px;
  overflow: hidden;
  margin-bottom: 22px;
  background: white;
}
.workflow-toolbar {
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
  align-items: center;
  justify-content: space-between;
  padding: 12px 14px;
  background: #f8fafc;
  border-bottom: 1px solid #dce3ec;
  font-size: 13px;
  font-weight: 600;
}
.workflow-toolbar small {
  font-size: 11px;
  color: #64748b;
  margin-left: 8px;
  font-weight: 400;
}
.workflow-toolbar > div {
  display: flex;
  gap: 5px;
}
.workflow-toolbar button {
  border: 1px solid #cbd5e1;
  border-radius: 5px;
  padding: 4px 9px;
  background: white;
  color: #334155;
}
.workflow-viewport {
  overflow: auto;
  max-height: 620px;
  height: 480px;
  touch-action: pan-x pan-y;
  cursor: grab;
}
.workflow-sheet {
  position: relative;
  transform-origin: 0 0;
  background: radial-gradient(#d5dde8 1px, transparent 1px);
  background-size: 20px 20px;
}
.workflow-lane {
  position: absolute;
  top: 20px;
  width: 248px;
  font-size: 11px;
  text-transform: uppercase;
  letter-spacing: 0.65px;
  font-weight: 600;
  color: #64748b;
}
.workflow-connectors {
  position: absolute;
  inset: 0;
  pointer-events: none;
}
.workflow-node {
  position: absolute;
  display: flex;
  flex-direction: column;
  text-align: left;
  padding: 14px 16px;
  border: 1.5px solid #94a3b8;
  border-top: 4px solid #64748b;
  border-radius: 18px;
  background: #f8fafc;
  box-shadow: 0 3px 8px #0f172a0b;
  cursor: pointer;
  touch-action: none;
  color: #1e293b;
}
.workflow-node.selected {
  outline: 3px solid #3b82f6;
  outline-offset: 3px;
}
.workflow-node.rejected {
  opacity: 0.65;
  border-style: dashed;
}
.workflow-node-kind {
  font-weight: 700;
  font-size: 11px;
  line-height: 1.35;
  max-height: 30px;
  overflow: hidden;
}
.workflow-node-description {
  font-size: 13px;
  line-height: 1.45;
  margin-top: 7px;
  display: -webkit-box;
  -webkit-line-clamp: 3;
  -webkit-box-orient: vertical;
  overflow: hidden;
  overflow-wrap: anywhere;
}
.workflow-node-meta {
  margin-top: auto;
  padding-top: 6px;
  font-size: 9px;
  color: #475569;
}
.workflow-node-evidence {
  font-size: 10px;
  color: #64748b;
  margin-top: 3px;
}
.node-event-information {
  background: #eff6ff;
  border-color: #60a5fa;
}
.node-contributing-factor {
  background: #fffbeb;
  border-color: #eab308;
}
.node-direct-factor {
  background: #fff7ed;
  border-color: #f97316;
}
.node-actual-event {
  background: #fff1f2;
  border-color: #f43f5e;
  border-radius: 30px;
}
.node-post-event {
  background: #ecfdf5;
  border-color: #10b981;
}
.node-root-cause {
  background: #f5f3ff;
  border-color: #8b5cf6;
}
.workflow-caption {
  font-size: 11px;
  line-height: 1.6;
  padding: 10px 14px;
  color: #64748b;
  margin: 0;
  border-top: 1px solid #e2e8f0;
}
@media (max-width: 760px) {
  .workflow-viewport {
    height: 380px;
  }
  .workflow-toolbar small {
    display: block;
    margin: 3px 0 0;
  }
}
</style>

<script setup lang="ts">
import { nextTick, onBeforeUnmount, onMounted, ref, shallowRef, watch } from 'vue'
import DOMPurify from 'dompurify'
import * as L from 'leaflet'
import 'leaflet/dist/leaflet.css'
import pinImage from 'leaflet/dist/images/marker-icon.png'
import pinImage2x from 'leaflet/dist/images/marker-icon-2x.png'
import pinShadow from 'leaflet/dist/images/marker-shadow.png'
import { scheduleRange, type ScheduleTask } from '../lib/ganttSchedule'

export type TaskLocation = {
  task: ScheduleTask
  contractor: string
  location: string | null
}

export type ProjectMapSettings = {
  center_latitude: number
  center_longitude: number
  default_zoom: number
  min_zoom: number
  max_zoom: number
  default_tile_url: string
  default_attribution: string
  satellite_tile_url: string
  satellite_attribution: string
}

const props = defineProps<{ locations: TaskLocation[]; settings: ProjectMapSettings }>()
const emit = defineEmits<{ select: [task: ScheduleTask] }>()
const mapHost = ref<HTMLElement | null>(null)
const hasLocations = ref(true)
const popup = shallowRef<{ host: HTMLElement; locations: TaskLocation[] } | null>(null)
const icon = L.icon({
  iconUrl: pinImage,
  iconRetinaUrl: pinImage2x,
  shadowUrl: pinShadow,
  iconSize: [25, 41],
  iconAnchor: [12, 41],
  popupAnchor: [1, -34],
  shadowSize: [41, 41],
})

let map: L.Map | undefined
let taskLayers: L.FeatureGroup | undefined
let observer: ResizeObserver | undefined

function readFeatures(location: TaskLocation['location']) {
  try {
    const geojson = typeof location === 'string' ? JSON.parse(location) : location
    if (!geojson) return []
    if (geojson.type === 'FeatureCollection') {
      return Array.isArray(geojson.features) ? geojson.features : []
    }
    return [geojson]
  } catch {
    return []
  }
}

function bindTaskPopup(layer: L.Layer, locations: TaskLocation[]) {
  const host = document.createElement('div')
  layer.bindPopup(host, { minWidth: 160, maxWidth: 280, maxHeight: 220 })
  layer.on('popupopen', async () => {
    popup.value = { host, locations }
    // Leaflet measures its popup before Vue inserts the content.
    await nextTick()
    if (popup.value?.host === host) layer.getPopup()?.update()
  })
  layer.on('popupclose', () => {
    if (popup.value?.host === host) popup.value = null
  })
}

function renderLocations() {
  if (!map || !taskLayers) return
  map.closePopup()
  taskLayers.clearLayers()
  const pins = new Map<string, { point: L.LatLng; locations: Map<string, TaskLocation> }>()

  function addLayer(layer: L.Layer, location: TaskLocation) {
    if (layer instanceof L.Marker) {
      const point = layer.getLatLng()
      const key = `${point.lat},${point.lng}`
      const pin = pins.get(key) || { point, locations: new Map<string, TaskLocation>() }
      pin.locations.set(location.task.name, location)
      pins.set(key, pin)
    } else if (layer instanceof L.LayerGroup) {
      layer.eachLayer((child) => addLayer(child, location))
    } else if (layer instanceof L.Path) {
      if (layer instanceof L.Polyline && !layer.getBounds().isValid()) return
      bindTaskPopup(layer, [location])
      taskLayers?.addLayer(layer)
    }
  }

  for (const location of props.locations) {
    for (const feature of readFeatures(location.location)) {
      try {
        const layers = L.geoJSON(feature, {
          pointToLayer: ({ properties }, point) => {
            // Frappe saves circles as GeoJSON points with their original radius.
            const radius = properties?.radius
            if (typeof radius === 'number' && Number.isFinite(radius) && radius > 0) {
              if (properties.point_type === 'circle') return L.circle(point, { radius })
              if (properties.point_type === 'circlemarker') return L.circleMarker(point, { radius })
            }
            return L.marker(point)
          },
          coordsToLatLng: ([lng, lat]) => {
            if (!Number.isFinite(lat) || !Number.isFinite(lng) || Math.abs(lat) > 90 || Math.abs(lng) > 180) {
              throw new Error('Invalid task location')
            }
            return L.latLng(lat, lng)
          },
        })
        addLayer(layers, location)
      } catch {
        // A malformed feature should leave the other task locations usable.
        continue
      }
    }
  }

  for (const { point, locations } of pins.values()) {
    const entries = [...locations.values()]
    const title = entries.length === 1 ? entries[0].task.title : `${entries.length} tasks at this location`
    const marker = L.marker(point, { icon, title, alt: title })
    bindTaskPopup(marker, entries)
    taskLayers.addLayer(marker)
  }

  const bounds = taskLayers.getBounds()
  hasLocations.value = bounds.isValid()
  if (hasLocations.value) {
    map.fitBounds(bounds, { padding: [28, 40], maxZoom: 16 })
  }
}

onMounted(() => {
  if (!mapHost.value) return
  const settings = props.settings
  const minZoom = Math.max(0, settings.min_zoom)
  const maxZoom = Math.max(minZoom, settings.max_zoom)
  const tileOptions = { minZoom, maxZoom }
  const attribution = (value: string) => DOMPurify.sanitize(value, {
    ALLOWED_TAGS: ['a'],
    ALLOWED_ATTR: ['href'],
  })
  const street = L.tileLayer(settings.default_tile_url, {
    ...tileOptions, attribution: attribution(settings.default_attribution),
  })
  const satellite = L.tileLayer(settings.satellite_tile_url, {
    ...tileOptions, attribution: attribution(settings.satellite_attribution),
  })
  map = L.map(mapHost.value, { layers: [street], scrollWheelZoom: false }).setView(
    [settings.center_latitude, settings.center_longitude], settings.default_zoom,
  )
  L.control.layers({ Street: street, Satellite: satellite }).addTo(map)
  taskLayers = L.featureGroup().addTo(map)
  renderLocations()

  observer = new ResizeObserver(() => map?.invalidateSize({ pan: false }))
  observer.observe(mapHost.value)
})

watch(() => props.locations, renderLocations)

onBeforeUnmount(() => {
  observer?.disconnect()
  map?.remove()
})
</script>

<template>
  <div
    v-show="hasLocations"
    ref="mapHost"
    class="project-map min-h-64 flex-1 overflow-hidden rounded-7 border border-outline-gray-2"
    role="region"
    aria-label="Work Summary locations"
  />
  <p v-if="!hasLocations" class="rounded-7 border border-outline-gray-1 bg-surface-base p-4 text-sm text-ink-gray-6">
    No active Work Summaries have a location on this map.
  </p>

  <Teleport v-if="popup" :to="popup.host">
    <ul class="divide-y divide-gray-200">
      <li v-for="{ task, contractor } in popup.locations" :key="task.name" class="py-2">
        <button
          type="button"
          class="min-h-11 w-full break-words rounded text-left text-sm font-semibold text-blue-700 underline focus-visible:outline focus-visible:outline-2"
          @click="emit('select', task)"
        >{{ task.title }}</button>
        <dl class="grid gap-1 text-xs text-gray-700">
          <div class="min-w-0">
            <dt class="font-semibold">Contractor</dt>
            <dd class="break-words">{{ contractor || '—' }}</dd>
          </div>
          <div>
            <dt class="font-semibold">Expected dates</dt>
            <dd>{{ scheduleRange(task) }}</dd>
          </div>
        </dl>
      </li>
    </ul>
  </Teleport>
</template>

<style scoped>
.project-map {
  isolation: isolate;
  touch-action: none;
}
</style>

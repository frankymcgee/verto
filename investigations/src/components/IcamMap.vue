<template>
  <div class="icam-map" aria-label="ICAM causal map">
    <div v-for="category in [...categories].reverse()" :key="category" class="map-column">
      <h4>{{ category }}</h4>
      <div
        v-for="factor in factors.filter(
          (row) => row.category === category && row.finding_status === 'Supported',
        )"
        :key="factor.entry_id"
        class="map-factor"
      >
        <code>{{ factor.entry_id }}</code>
        <p v-if="factor.factor_type">
          <strong>{{ factor.factor_type }}</strong>
        </p>
        <p>{{ factor.description }}</p>
        <small v-if="refs(factor.contributes_to).length"
          >Contributes to {{ refs(factor.contributes_to).join(', ') }}</small
        >
        <small v-else-if="category === categories[0]">Defence associated with the incident</small>
      </div>
      <p
        v-if="
          !factors.some((row) => row.category === category && row.finding_status === 'Supported')
        "
        class="help"
      >
        No supported factors recorded
      </p>
    </div>
  </div>
</template>
<script setup>
import { categories, refs } from '../model'
defineProps({ factors: { type: Array, default: () => [] } })
</script>

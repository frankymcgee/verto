<template>
  <div class="planner-table-surface">
    <slot />
  </div>
</template>

<!--
  Keep table rendering in its own component effect. Vue tracks the stable slot's
  grid dependencies here, so opening/closing a sibling dialog does not rebuild
  every roster cell. Data, filters, selections and drag previews still update.
-->
<style scoped>
.planner-table-surface {
  position: relative;
  isolation: isolate;
  z-index: 0;
  min-width: 0;
}
</style>

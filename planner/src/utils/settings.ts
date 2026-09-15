import { usePlannerBootstrap } from './bootstrap'

let settings: any

export function usePlannerSettings() {
  const bootstrap = usePlannerBootstrap()
  settings ??= {
    get data() { return bootstrap.data?.settings },
    get loading() { return bootstrap.loading },
    get fetched() { return bootstrap.fetched },
    get error() { return bootstrap.error },
    fetch: () => bootstrap.fetch({ sections: ['settings'] }),
  }
  return settings
}

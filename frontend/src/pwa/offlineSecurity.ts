const DB_NAME = 'verto-mobile-offline-db'
const DB_VERSION = 3
const API_CACHE_STORE = 'api_cache'

function openDatabase(): Promise<IDBDatabase> {
  return new Promise((resolve, reject) => {
    const request = indexedDB.open(DB_NAME, DB_VERSION)

    request.onerror = () => reject(request.error || new Error('Could not open offline cache.'))
    request.onsuccess = () => resolve(request.result)
  })
}

export async function clearOfflineReadCache() {
  const db = await openDatabase()

  try {
    if (!db.objectStoreNames.contains(API_CACHE_STORE)) {
      return
    }

    await new Promise<void>((resolve, reject) => {
      const transaction = db.transaction(API_CACHE_STORE, 'readwrite')
      const request = transaction.objectStore(API_CACHE_STORE).clear()

      request.onerror = () => reject(request.error || new Error('Could not clear offline cache.'))
      transaction.oncomplete = () => resolve()
      transaction.onerror = () => reject(transaction.error || new Error('Could not clear offline cache.'))
      transaction.onabort = () => reject(transaction.error || new Error('Could not clear offline cache.'))
    })
  } finally {
    db.close()
  }
}

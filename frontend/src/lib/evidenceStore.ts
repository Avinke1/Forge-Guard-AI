/**
 * Inspection evidence store - plain IndexedDB, this browser only.
 * DB "forgeguard-evidence", object store "files" (key "id", index "machine_id").
 * Files never leave the device: nothing here talks to the backend or the AI.
 */

export interface StoredEvidence {
  id: string;
  machine_id: string;
  name: string;
  type: string; // MIME type of the file
  size: number; // bytes
  added_at: string; // ISO 8601
  blob: Blob;
}

const DB_NAME = 'forgeguard-evidence';
const DB_VERSION = 1;
const STORE = 'files';
const BY_MACHINE = 'machine_id';

let dbPromise: Promise<IDBDatabase> | null = null;

function openDb(): Promise<IDBDatabase> {
  if (dbPromise) return dbPromise;
  dbPromise = new Promise<IDBDatabase>((resolve, reject) => {
    try {
      if (typeof indexedDB === 'undefined' || !indexedDB) {
        reject(new Error('IndexedDB is not available in this browser.'));
        return;
      }
      const req = indexedDB.open(DB_NAME, DB_VERSION);
      req.onupgradeneeded = () => {
        const db = req.result;
        if (!db.objectStoreNames.contains(STORE)) {
          const store = db.createObjectStore(STORE, { keyPath: 'id' });
          store.createIndex(BY_MACHINE, 'machine_id', { unique: false });
        }
      };
      req.onsuccess = () => {
        const db = req.result;
        db.onversionchange = () => db.close();
        resolve(db);
      };
      req.onerror = () => reject(req.error || new Error('Could not open IndexedDB.'));
      req.onblocked = () => reject(new Error('IndexedDB is blocked by another tab.'));
    } catch (e) {
      reject(e instanceof Error ? e : new Error(String(e)));
    }
  });
  // A failed open must not stick: the next call tries again.
  dbPromise.catch(() => {
    dbPromise = null;
  });
  return dbPromise;
}

function run<T>(mode: IDBTransactionMode, work: (store: IDBObjectStore) => IDBRequest<T>): Promise<T> {
  return openDb().then(
    (db) =>
      new Promise<T>((resolve, reject) => {
        try {
          const tx = db.transaction(STORE, mode);
          const req = work(tx.objectStore(STORE));
          let result: T;
          req.onsuccess = () => {
            result = req.result;
          };
          tx.oncomplete = () => resolve(result);
          tx.onerror = () => reject(tx.error || req.error || new Error('IndexedDB request failed.'));
          tx.onabort = () => reject(tx.error || new Error('IndexedDB transaction aborted (storage full?).'));
        } catch (e) {
          reject(e instanceof Error ? e : new Error(String(e)));
        }
      })
  );
}

/** All saved files of one machine, oldest first. */
export async function listFiles(machineId: string): Promise<StoredEvidence[]> {
  const rows = await run<StoredEvidence[]>('readonly', (s) => s.index(BY_MACHINE).getAll(machineId));
  return (rows || []).sort((a, b) => a.added_at.localeCompare(b.added_at));
}

export async function addFile(record: StoredEvidence): Promise<void> {
  await run('readwrite', (s) => s.put(record));
}

export async function removeFile(id: string): Promise<void> {
  await run('readwrite', (s) => s.delete(id));
}

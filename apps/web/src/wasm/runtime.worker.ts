import type { WorkerRequest, WorkerResponse } from './protocol'
import { WorkerRuntimeHost, type WasmRuntime } from './worker-runtime'

interface GeneratedWasmModule {
  default(input: { module_or_path: string }): Promise<unknown>
  ShowcaseRuntime: new () => WasmRuntime
}

interface WorkerScope {
  location: Location
  addEventListener(type: 'message', listener: (event: MessageEvent<WorkerRequest>) => void): void
  postMessage(response: WorkerResponse): void
}

function publicAssetUrl(file: string): string {
  const base = import.meta.env.BASE_URL.endsWith('/')
    ? import.meta.env.BASE_URL
    : `${import.meta.env.BASE_URL}/`
  return new URL(`${base}wasm/${file}`, globalThis.location.origin).href
}

async function loadRuntime(): Promise<WasmRuntime> {
  const moduleUrl = publicAssetUrl('showcase_wasm.js')
  const wasmUrl = publicAssetUrl('showcase_wasm_bg.wasm')
  const module = await import(/* @vite-ignore */ moduleUrl) as GeneratedWasmModule
  await module.default({ module_or_path: wasmUrl })
  return new module.ShowcaseRuntime()
}

const scope = globalThis as unknown as WorkerScope
const host = new WorkerRuntimeHost(loadRuntime)

scope.addEventListener('message', (event) => {
  void host.handle(event.data).then(response => scope.postMessage(response))
})

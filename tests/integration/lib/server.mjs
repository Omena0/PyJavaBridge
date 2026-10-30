import { createHash } from 'node:crypto'
import { spawn } from 'node:child_process'
import fs from 'node:fs'
import fsp from 'node:fs/promises'
import net from 'node:net'
import path from 'node:path'
import { fileURLToPath } from 'node:url'

const HERE = path.dirname(fileURLToPath(import.meta.url))
export const INTEGRATION_DIR = path.resolve(HERE, '..')
export const CACHE_DIR = path.join(INTEGRATION_DIR, '.cache')
const SERVER_DIR = path.join(INTEGRATION_DIR, '.server')
const PAPER_VERSION = process.env.PJB_MC_VERSION || '1.21.4'
const PAPER_BUILD = process.env.PJB_PAPER_BUILD || '232'
const PAPER_API = `https://fill.papermc.io/v3/projects/paper/versions/${PAPER_VERSION}/builds`
const PROTOCOL_LIB_URL = process.env.PJB_PROTOCOL_LIB_URL ||
  'https://repo.dmulloy2.net/repository/public/com/comphenix/protocol/ProtocolLib/5.3.0/ProtocolLib-5.3.0.jar'
export const TEST_BOT_NAME = 'PJBBot'
export const TEST_BOT_2_NAME = 'PJBBot2'
const DEFAULT_PORT = Number(process.env.PJB_TEST_PORT || 25599)

function log (...args) {
  console.log('[pjb-test]', ...args)
}

async function download (url, destination) {
  if (fs.existsSync(destination) && fs.statSync(destination).size > 0) return destination
  log(`downloading ${url}`)
  const response = await fetch(url, { redirect: 'follow' })
  if (!response.ok) throw new Error(`Failed to download ${url}: HTTP ${response.status}`)
  const data = Buffer.from(await response.arrayBuffer())
  await fsp.writeFile(destination, data)
  return destination
}

async function resolveServerJar () {
  const explicit = process.env.PJB_SERVER_JAR
  if (explicit) return path.resolve(explicit)

  const localCandidates = [
    path.resolve(INTEGRATION_DIR, '../../server/leaf-1.21.4-524.jar'),
    path.resolve(INTEGRATION_DIR, '../../server/leaf-1.21.11-49.jar'),
  ]
  if (!process.env.PJB_FORCE_DOWNLOAD) {
    for (const candidate of localCandidates) {
      if (fs.existsSync(candidate)) return candidate
    }
  }

  await fsp.mkdir(CACHE_DIR, { recursive: true })
  const destination = path.join(CACHE_DIR, `paper-${PAPER_VERSION}-${PAPER_BUILD}.jar`)
  if (fs.existsSync(destination) && fs.statSync(destination).size > 0) return destination

  const response = await fetch(PAPER_API)
  if (!response.ok) throw new Error(`Failed to query Paper builds: HTTP ${response.status}`)
  const builds = await response.json()
  const build = builds.find(entry => String(entry.id) === String(PAPER_BUILD)) || builds[0]
  const downloadUrl = build?.downloads?.['server:default']?.url
  if (!downloadUrl) throw new Error('Could not find a Paper server download URL')
  return download(downloadUrl, destination)
}

async function resolveProtocolLib () {
  const explicit = process.env.PJB_PROTOCOL_LIB
  if (explicit) return path.resolve(explicit)
  if (process.env.PJB_SKIP_PROTOCOL_LIB) return null
  const local = path.resolve(INTEGRATION_DIR, '../../server/plugins/ProtocolLib.jar')
  if (fs.existsSync(local) && !process.env.PJB_FORCE_DOWNLOAD) return local
  await fsp.mkdir(CACHE_DIR, { recursive: true })
  const destination = path.join(CACHE_DIR, 'ProtocolLib-5.3.0.jar')
  try {
    return await download(PROTOCOL_LIB_URL, destination)
  } catch (error) {
    log(`ProtocolLib unavailable, packet tests will be skipped: ${error.message}`)
    return null
  }
}

export function offlineUuid (name) {
  const hash = createHash('md5').update(`OfflinePlayer:${name}`, 'utf8').digest()
  hash[6] = (hash[6] & 0x0f) | 0x30
  hash[8] = (hash[8] & 0x3f) | 0x80
  const hex = hash.toString('hex')
  return `${hex.slice(0, 8)}-${hex.slice(8, 12)}-${hex.slice(12, 16)}-${hex.slice(16, 20)}-${hex.slice(20)}`
}

async function findFreePort (start) {
  for (let port = start; port < start + 100; port++) {
    const available = await new Promise(resolve => {
      const server = net.createServer()
      server.unref()
      server.once('error', () => resolve(false))
      server.listen({ port, host: '127.0.0.1' }, () => server.close(() => resolve(true)))
    })
    if (available) return port
  }
  throw new Error(`No free port found near ${start}`)
}

function writeFile (file, contents) {
  fs.writeFileSync(file, contents)
}

async function waitForFile (file, timeoutMs, label) {
  const deadline = Date.now() + timeoutMs
  while (Date.now() < deadline) {
    if (fs.existsSync(file)) return
    await new Promise(resolve => setTimeout(resolve, 100))
  }
  throw new Error(`Timed out waiting for ${label || file}`)
}

function waitForLine (child, pattern, timeoutMs, label) {
  return new Promise((resolve, reject) => {
    let buffer = ''
    const timer = setTimeout(() => {
      cleanup()
      reject(new Error(`Timed out waiting for ${label || pattern} in server output`))
    }, timeoutMs)
    const onData = chunk => {
      buffer += chunk.toString()
      const match = buffer.match(pattern)
      if (match) {
        cleanup()
        resolve(match)
      }
    }
    const onExit = code => {
      cleanup()
      reject(new Error(`Server exited with code ${code} while waiting for ${label || pattern}`))
    }
    const cleanup = () => {
      clearTimeout(timer)
      child.stdout.off('data', onData)
      child.stderr.off('data', onData)
      child.off('exit', onExit)
    }
    child.stdout.on('data', onData)
    child.stderr.on('data', onData)
    child.once('exit', onExit)
  })
}

export class TestServer {
  constructor (options = {}) {
    this.options = options
    this.dir = options.dir || SERVER_DIR
    this.port = options.port || DEFAULT_PORT
    this.child = null
    this.stdout = []
    this.ready = false
    this.packetApi = false
  }

  get dataDir () {
    return path.join(this.dir, 'plugins', 'PyJavaBridge')
  }

  get requestDir () {
    return path.join(this.dataDir, 'test-requests')
  }

  get resultDir () {
    return path.join(this.dataDir, 'test-results')
  }

  async prepare () {
    const serverJar = await resolveServerJar()
    const protocolLib = await resolveProtocolLib()
    this.protocolLib = protocolLib
    this.port = await findFreePort(this.port)

    await fsp.rm(this.dir, { recursive: true, force: true })
    await fsp.mkdir(path.join(this.dir, 'plugins'), { recursive: true })
    await fsp.mkdir(path.join(this.dir, 'config'), { recursive: true })
    await fsp.mkdir(path.join(this.dataDir, 'scripts'), { recursive: true })
    await fsp.mkdir(this.requestDir, { recursive: true })
    await fsp.mkdir(this.resultDir, { recursive: true })
    await fsp.mkdir(path.join(this.dir, 'logs'), { recursive: true })

    writeFile(path.join(this.dir, 'eula.txt'), 'eula=true\n')
    writeFile(path.join(this.dir, 'server.properties'), [
      'online-mode=false',
      'enforce-secure-profile=false',
      `server-port=${this.port}`,
      'server-ip=127.0.0.1',
      'max-players=20',
      'view-distance=4',
      'simulation-distance=4',
      'level-name=world',
      'level-seed=12345',
      'level-type=minecraft\\:flat',
      'generate-structures=false',
      'spawn-protection=0',
      'enable-command-block=true',
      'allow-flight=true',
      'allow-nether=true',
      'difficulty=normal',
      'gamemode=creative',
      'motd=PJB Integration Server',
      'enable-status=true',
      'enable-query=false',
      'enable-rcon=false',
      'sync-chunk-writes=false',
      'max-tick-time=-1',
      'log-ips=false',
      '',
    ].join('\n'))
    writeFile(path.join(this.dir, 'bukkit.yml'), 'settings:\n  allow-end: true\n')
    writeFile(path.join(this.dir, 'ops.json'), JSON.stringify([
      { uuid: offlineUuid(TEST_BOT_NAME), name: TEST_BOT_NAME, level: 4, bypassesPlayerLimit: false },
      { uuid: offlineUuid(TEST_BOT_2_NAME), name: TEST_BOT_2_NAME, level: 4, bypassesPlayerLimit: false },
    ], null, 2))
    writeFile(path.join(this.dir, 'whitelist.json'), '[]\n')
    writeFile(path.join(this.dir, 'banned-players.json'), '[]\n')
    writeFile(path.join(this.dir, 'banned-ips.json'), '[]\n')

    const pluginJar = await this.resolvePluginJar()
    await fsp.copyFile(pluginJar, path.join(this.dir, 'plugins', path.basename(pluginJar)))
    if (protocolLib) {
      await fsp.copyFile(protocolLib, path.join(this.dir, 'plugins', 'ProtocolLib.jar'))
    }

    const probe = path.resolve(INTEGRATION_DIR, 'scripts', 'probe.py')
    await fsp.copyFile(probe, path.join(this.dataDir, 'scripts', 'pjb_probe.py'))

    this.serverJar = serverJar
  }

  async resolvePluginJar () {
    if (process.env.PJB_PLUGIN_JAR) return path.resolve(process.env.PJB_PLUGIN_JAR)
    const libs = path.resolve(INTEGRATION_DIR, '../../build/libs')
    if (fs.existsSync(libs)) {
      const jars = fs.readdirSync(libs)
        .filter(name => name.endsWith('.jar') && !name.includes('-sources') && !name.includes('-javadoc'))
        .map(name => path.join(libs, name))
        .sort((a, b) => fs.statSync(b).mtimeMs - fs.statSync(a).mtimeMs)
      if (jars.length) return jars[0]
    }
    throw new Error('Plugin jar not found; run ./gradlew shadowJar or set PJB_PLUGIN_JAR')
  }

  async start () {
    if (this.ready) return this
    await this.prepare()

    const args = [
      '-Xms512M',
      '-Xmx2G',
      '-XX:+UseG1GC',
      '-Dcom.mojang.eula.agree=true',
      '-Ddisable.watchdog=true',
      '-jar',
      this.serverJar,
      '--nogui',
    ]
    log(`starting server on port ${this.port}`)
    this.child = spawn('java', args, { cwd: this.dir, stdio: ['pipe', 'pipe', 'pipe'] })
    const record = chunk => {
      const text = chunk.toString()
      this.stdout.push(text)
      if (process.env.PJB_TEST_VERBOSE) process.stdout.write(text)
    }
    this.child.stdout.on('data', record)
    this.child.stderr.on('data', record)

    await waitForLine(this.child, /Done \([\d.]+s\)! For help/, 180_000, 'server startup')
    this.ready = true
    await waitForFile(path.join(this.dataDir, '.probe-ready'), 60_000, 'test probe readiness')

    const readyPath = path.join(this.dataDir, '.probe-info.json')
    await waitForFile(readyPath, 10_000, 'test probe info')
    this.info = JSON.parse(await fsp.readFile(readyPath, 'utf8'))
    this.packetApi = !!this.info.packet_api
    log(`server ready (packet api: ${this.packetApi})`)
    return this
  }

  async stop () {
    if (!this.child) return
    const child = this.child
    this.child = null
    this.ready = false
    if (child.exitCode !== null) return
    child.stdin.write('stop\n')
    await new Promise(resolve => {
      const timer = setTimeout(() => {
        child.kill('SIGKILL')
        resolve()
      }, 30_000)
      child.once('exit', () => {
        clearTimeout(timer)
        resolve()
      })
    })
  }

  async writeRequest (id, payload) {
    await fsp.mkdir(this.requestDir, { recursive: true })
    const file = path.join(this.requestDir, `${id}.json`)
    await fsp.writeFile(file, JSON.stringify(payload))
    return file
  }

  async readResult (id) {
    const file = path.join(this.resultDir, `${id}.json`)
    return JSON.parse(await fsp.readFile(file, 'utf8'))
  }

  async waitForResult (id, timeoutMs = 30_000) {
    const file = path.join(this.resultDir, `${id}.json`)
    await waitForFile(file, timeoutMs, `result ${id}`)
    for (let i = 0; i < 50; i++) {
      try {
        return JSON.parse(await fsp.readFile(file, 'utf8'))
      } catch (error) {
        if (error.code !== 'ENOENT' && !(error instanceof SyntaxError)) throw error
        await new Promise(resolve => setTimeout(resolve, 50))
      }
    }
    throw new Error(`Could not read result ${id}`)
  }

  tail (lines = 80) {
    return this.stdout.join('').split('\n').slice(-lines).join('\n')
  }
}

let singleton = null

export async function getServer () {
  if (!singleton) {
    singleton = new TestServer()
    await singleton.start()
  }
  return singleton
}

export async function stopServer () {
  if (!singleton) return
  const server = singleton
  singleton = null
  await server.stop()
}

process.on('exit', () => {
  if (singleton?.child) {
    try { singleton.child.kill('SIGKILL') } catch {}
  }
})

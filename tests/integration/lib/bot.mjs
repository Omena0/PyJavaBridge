import { randomUUID } from 'node:crypto'
import mineflayer from 'mineflayer'
import { TestServer, TEST_BOT_NAME, TEST_BOT_2_NAME } from './server.mjs'

export function delay (ms) {
  return new Promise(resolve => setTimeout(resolve, ms))
}

export async function waitForChat (bot, predicate, { timeout = 15_000, label = 'chat message' } = {}) {
  const matcher = typeof predicate === 'string'
    ? message => message.includes(predicate)
    : predicate
  return await new Promise((resolve, reject) => {
    const timer = setTimeout(() => {
      cleanup()
      reject(new Error(`Timed out waiting for ${label}. Recent chat: ${JSON.stringify(bot.__chatHistory?.slice(-10))}`))
    }, timeout)
    const onMessage = (message) => {
      const text = message.toString()
      if (matcher(text)) {
        cleanup()
        resolve(text)
      }
    }
    const onEnd = () => {
      cleanup()
      reject(new Error(`Bot disconnected while waiting for ${label}`))
    }
    const cleanup = () => {
      clearTimeout(timer)
      bot.off('messagestr', onMessage)
      bot.off('end', onEnd)
    }
    bot.on('messagestr', onMessage)
    bot.on('end', onEnd)
  })
}

export async function connectBot (server, options = {}) {
  const username = options.username || TEST_BOT_NAME
  const bot = mineflayer.createBot({
    host: '127.0.0.1',
    port: server.port,
    username,
    auth: 'offline',
    version: options.version || process.env.PJB_MC_VERSION || '1.21.4',
    hideErrors: !process.env.PJB_TEST_VERBOSE,
  })
  bot.__chatHistory = []
  bot.on('messagestr', message => {
    const text = message.toString()
    bot.__chatHistory.push(text)
    if (bot.__chatHistory.length > 200) bot.__chatHistory.shift()
  })
  bot.on('kicked', reason => {
    if (process.env.PJB_TEST_VERBOSE) console.error('bot kicked:', reason)
  })

  await new Promise((resolve, reject) => {
    const timer = setTimeout(() => {
      cleanup()
      reject(new Error(`Timed out connecting bot ${username}. Server log:\n${server.tail(40)}`))
    }, 60_000)
    const onSpawn = () => {
      cleanup()
      resolve()
    }
    const onError = error => {
      cleanup()
      reject(error)
    }
    const onEnd = reason => {
      cleanup()
      reject(new Error(`Bot ${username} disconnected before spawn: ${reason}`))
    }
    const cleanup = () => {
      clearTimeout(timer)
      bot.off('spawn', onSpawn)
      bot.off('error', onError)
      bot.off('end', onEnd)
    }
    bot.once('spawn', onSpawn)
    bot.once('error', onError)
    bot.once('end', onEnd)
  })

  bot.__username = username
  return bot
}

export async function connectSecondBot (server, options = {}) {
  return connectBot(server, { ...options, username: options.username || TEST_BOT_2_NAME })
}

export async function closeBot (bot) {
  if (!bot) return
  try {
    bot.quit('test complete')
  } catch {}
  await delay(100)
}

export async function runCase (server, bot, caseName, data = {}, options = {}) {
  const id = `${caseName.replace(/[^a-z0-9_-]/gi, '_')}-${randomUUID()}`
  await server.writeRequest(id, { case: caseName, data })
  const marker = new RegExp(`PJBIT:${id.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')}:(ok|fail)`)
  const wait = waitForChat(bot, text => marker.test(text), {
    timeout: options.timeout || 30_000,
    label: `result marker for ${caseName}`,
  })
  bot.chat(`/pjbtest ${caseName} ${id}`)
  const line = await wait
  const status = marker.exec(line)[1]
  const result = await server.waitForResult(id, options.timeout || 30_000)
  if (status === 'fail' || !result.ok) {
    const error = new Error(`Probe case ${caseName} failed: ${result.error || 'unknown error'}`)
    error.result = result
    throw error
  }
  return result.value
}

export async function command (bot, text, options = {}) {
  const label = options.label || `command ${text}`
  const response = options.expect ? waitForChat(bot, options.expect, { timeout: options.timeout, label }) : null
  bot.chat(text)
  return response ? await response : null
}

export function position (bot) {
  return bot.entity?.position
}

export { TestServer, TEST_BOT_NAME, TEST_BOT_2_NAME }

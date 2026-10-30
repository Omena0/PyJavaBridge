import { getServer, stopServer } from './tests/integration/lib/server.mjs'
import { connectBot, runCase, closeBot } from './tests/integration/lib/bot.mjs'
try {
  const server = await getServer()
  console.log('SERVER_READY')
  const bot = await connectBot(server)
  console.log('BOT_READY')
  const res = await runCase(server, bot, 'ping', { message: 'hi' })
  console.log('RES=' + JSON.stringify(res))
  await closeBot(bot)
  await stopServer()
  process.exit(0)
} catch (e) {
  console.error('ERR:' + e.message)
  console.error(e.stack?.split('\n').slice(0, 10).join('\n'))
  try { await stopServer() } catch {}
  process.exit(1)
}

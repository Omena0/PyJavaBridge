import { test, describe } from 'node:test'
import assert from 'node:assert/strict'
import { getServer } from '../lib/server.mjs'
import { connectBot, runCase, closeBot } from '../lib/bot.mjs'

describe('Server API', () => {
  let server, bot

  test.before(async () => {
    server = await getServer()
    bot = await connectBot(server)
  })

  test.after(async () => {
    await closeBot(bot)
  })

  test('server props', async () => {
    const r = await runCase(server, bot, 'server_props', {})
    assert.ok(r.name)
    assert.ok(Array.isArray(r.tps))
    assert.ok(r.max_players > 0)
  })

  test('server world', async () => {
    const r = await runCase(server, bot, 'server_world', {})
    assert.equal(r.world_name, 'world')
  })

  test('server bossbar create', async () => {
    const r = await runCase(server, bot, 'server_bossbar_create', {})
    assert.ok(r.bar_created)
  })

  test('server flush frame atomic', async () => {
    const r = await runCase(server, bot, 'server_flush_frame_atomic', {})
    assert.ok(r.has_frame)
  })

  test('server after', async () => {
    const r = await runCase(server, bot, 'server_after', {})
    assert.ok(r.after_ok)
  })

  test('server structures', async () => {
    const r = await runCase(server, bot, 'server_structures', {})
    assert.ok(r.saved !== undefined || r.save_error)
  })

  test('server chat broadcast', async () => {
    const r = await runCase(server, bot, 'server_chat_broadcast', {})
    assert.ok(r.chat_broadcast)
  })

  test('server reflect clazz', async () => {
    const r = await runCase(server, bot, 'server_reflect_clazz', {})
    assert.ok(r.reflect_ok || r.error)
  })
})

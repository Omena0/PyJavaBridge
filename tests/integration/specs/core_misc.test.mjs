import { test, describe } from 'node:test'
import assert from 'node:assert/strict'
import { getServer } from '../lib/server.mjs'
import { connectBot, runCase, closeBot } from '../lib/bot.mjs'

describe('Core Misc API', () => {
  let server, bot

  test.before(async () => {
    server = await getServer()
    bot = await connectBot(server)
  })

  test.after(async () => {
    await closeBot(bot)
  })

  test('decorators presence', async () => {
    const r = await runCase(server, bot, 'decorators_presence', {})
    assert.ok(r.has_event)
  })

  test('exceptions', async () => {
    const r = await runCase(server, bot, 'exceptions', {})
    assert.ok(r.BridgeError)
  })

  test('console player', async () => {
    const r = await runCase(server, bot, 'console_player', {})
    assert.ok(r.ConsolePlayer)
  })

  test('world time constants', async () => {
    const r = await runCase(server, bot, 'world_time_constants', {})
    assert.ok(r.noon_ticks === 6000)
  })

  test('player open book method', async () => {
    const r = await runCase(server, bot, 'player_open_book', {})
    assert.ok(r.open_book_method)
  })

  test('player set resource pack method', async () => {
    const r = await runCase(server, bot, 'player_set_resource_pack', {})
    assert.ok(r.method_exists)
  })

  test('world at time method', async () => {
    const r = await runCase(server, bot, 'world_at_time', {})
    assert.ok(r.has_at_time)
  })

  test('world get chunk async', async () => {
    const r = await runCase(server, bot, 'world_get_chunk_at_async', {})
    assert.ok(r.chunk)
  })

  test('world spawn helpers', async () => {
    const r = await runCase(server, bot, 'world_spawn_at_player_spawn_projectile', {})
    assert.ok(r.has_spawn_at_player)
  })

  test('location arithmetic', async () => {
    const r = await runCase(server, bot, 'location_arithmetic', {})
    assert.ok(r.ok)
  })

  test('block create method', async () => {
    const r = await runCase(server, bot, 'block_create', {})
    assert.ok(r.has_create)
  })

  test('entity pathfind method', async () => {
    const r = await runCase(server, bot, 'entity_pathfind', {})
    assert.ok(r.has_pathfind)
  })

  test('inventory menu open', async () => {
    const r = await runCase(server, bot, 'inventory_menu_open_close', {})
    assert.ok(r.has_open)
  })

  test('item methods', async () => {
    const r = await runCase(server, bot, 'item_methods', {})
    assert.ok(r.has_drop)
  })

  test('advancement method', async () => {
    const r = await runCase(server, bot, 'advancement', {})
    assert.ok(r.has_grant)
  })

  test('enchantment', async () => {
    const r = await runCase(server, bot, 'enchantment', {})
    assert.ok(r.sharpness)
  })
})

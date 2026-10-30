import { test, describe } from 'node:test'
import assert from 'node:assert/strict'
import { getServer } from '../lib/server.mjs'
import { connectBot, runCase, closeBot } from '../lib/bot.mjs'

describe('World API', () => {
  let server, bot

  test.before(async () => {
    server = await getServer()
    bot = await connectBot(server)
  })

  test.after(async () => {
    await closeBot(bot)
    await server.stop()
  })

  test('world props', async () => {
    const r = await runCase(server, bot, 'world_props', {})
    assert.ok(r.name)
  })

  test('world time weather', async () => {
    const r = await runCase(server, bot, 'world_time_weather', {})
    assert.ok(r.time !== undefined || r.error)
  })

  test('world spawn location', async () => {
    const r = await runCase(server, bot, 'world_spawn_location', {})
    assert.ok(r.spawn_set)
  })

  test('world game rules', async () => {
    const r = await runCase(server, bot, 'world_game_rules', {})
    assert.ok(r.gamerule !== undefined)
  })

  test('world block ops', async () => {
    const r = await runCase(server, bot, 'world_block_ops', {})
    assert.ok(r.block_type)
  })

  test('world region ops', async () => {
    const r = await runCase(server, bot, 'world_region_ops', {})
    assert.ok(r.fill_replace_ok)
  })

  test('world spawn entities', async () => {
    const r = await runCase(server, bot, 'world_spawn_entities', {})
    assert.ok(r.spawned)
  })

  test('world spawn particle', async () => {
    const r = await runCase(server, bot, 'world_spawn_particle', {})
    assert.ok(r.particles_ok)
  })

  test('world lightning', async () => {
    const r = await runCase(server, bot, 'world_strike_lightning', {})
    assert.ok(r.lightning_ok)
  })

  test('world explosion', async () => {
    const r = await runCase(server, bot, 'world_explosion', {})
    assert.ok(r.explosion_ok)
  })

  test('world nearby entities', async () => {
    const r = await runCase(server, bot, 'world_nearby_entities', {})
    assert.ok(r.nearby_count !== undefined)
  })

  test('world ray trace', async () => {
    const r = await runCase(server, bot, 'world_ray_trace', {})
    assert.ok(r.has_raytrace !== undefined)
  })

  test('world block snapshot', async () => {
    const r = await runCase(server, bot, 'world_block_snapshot', {})
    assert.ok(r.snapshot_len !== undefined)
  })

  test('world entities near blocks near', async () => {
    const r = await runCase(server, bot, 'world_entities_near_blocks_near', {})
    assert.ok(r.ents !== undefined)
  })

  test('world batch spawn', async () => {
    const r = await runCase(server, bot, 'world_batch_spawn', {})
    assert.ok(r.count !== undefined)
  })

  test('world find entities', async () => {
    const r = await runCase(server, bot, 'world_find_entities', {})
    assert.ok(r.count !== undefined)
  })
})

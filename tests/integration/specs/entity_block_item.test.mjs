import { test, describe } from 'node:test'
import assert from 'node:assert/strict'
import { getServer } from '../lib/server.mjs'
import { connectBot, runCase, closeBot } from '../lib/bot.mjs'

describe('Entity Block Item API', () => {
  let server, bot

  test.before(async () => {
    server = await getServer()
    bot = await connectBot(server)
  })

  test.after(async () => {
    await closeBot(bot)
  })

  test('entity spawn props', async () => {
    const r = await runCase(server, bot, 'entity_spawn_props', {})
    assert.ok(r.uuid)
  })

  test('entity teleport velocity', async () => {
    const r = await runCase(server, bot, 'entity_teleport_velocity', {})
    assert.ok(r.teleport_vel_ok)
  })

  test('entity damage', async () => {
    const r = await runCase(server, bot, 'entity_damage', {})
    assert.ok(r.damaged)
  })

  test('entity tags metadata', async () => {
    const r = await runCase(server, bot, 'entity_tags_metadata', {})
    assert.ok(r.tagged)
  })

  test('block props', async () => {
    const r = await runCase(server, bot, 'block_props', {})
    assert.ok(r.type)
  })

  test('block drops', async () => {
    const r = await runCase(server, bot, 'block_drops', {})
    assert.ok(r.drops_count !== undefined)
  })

  test('block pdc', async () => {
    const r = await runCase(server, bot, 'block_pdc', {})
    assert.ok(r.pdc)
  })

  test('chunk ops', async () => {
    const r = await runCase(server, bot, 'chunk_ops', {})
    assert.ok(r.x !== undefined)
  })

  test('location ops', async () => {
    const r = await runCase(server, bot, 'location_ops', {})
    assert.ok(r.dist >= 0)
  })

  test('vector ops', async () => {
    const r = await runCase(server, bot, 'vector_ops', {})
    assert.ok(r.len > 0)
  })

  test('itembuilder', async () => {
    const r = await runCase(server, bot, 'itembuilder', {})
    assert.ok(r.name)
  })

  test('inventory ops', async () => {
    const r = await runCase(server, bot, 'inventory_ops', {})
    assert.ok(r.has !== undefined)
  })

  test('recipe', async () => {
    const r = await runCase(server, bot, 'recipe', {})
    assert.ok(r.has_shaped)
  })

  test('entity subtypes', async () => {
    const r = await runCase(server, bot, 'entity_subtypes', {})
    assert.ok(r.ArmorStand)
  })
})

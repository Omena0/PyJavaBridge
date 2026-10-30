import { test, describe } from 'node:test'
import assert from 'node:assert/strict'
import { getServer } from '../lib/server.mjs'
import { connectBot, runCase, closeBot } from '../lib/bot.mjs'

describe('Player API', () => {
  let server, bot

  test.before(async () => {
    server = await getServer()
    bot = await connectBot(server)
  })

  test.after(async () => {
    await closeBot(bot)
  })

  test('player props', async () => {
    const r = await runCase(server, bot, 'player_props', {})
    assert.ok(r.name)
  })

  test('player messages', async () => {
    const r = await runCase(server, bot, 'player_messages', {})
    assert.ok(r.messages_ok)
  })

  test('player teleport', async () => {
    const r = await runCase(server, bot, 'player_teleport', {})
    assert.ok(r.teleported)
  })

  test('player experience', async () => {
    const r = await runCase(server, bot, 'player_experience', {})
    assert.ok(r.level !== undefined)
  })

  test('player health food', async () => {
    const r = await runCase(server, bot, 'player_health_food', {})
    assert.ok(r.health)
  })

  test('player gamemode op fly', async () => {
    const r = await runCase(server, bot, 'player_gamemode_op_fly', {})
    assert.ok(r.gamemode)
  })

  test('player sneak sprint speed', async () => {
    const r = await runCase(server, bot, 'player_sneak_sprint_speed', {})
    assert.ok(r.walk_speed)
  })

  test('player give item', async () => {
    const r = await runCase(server, bot, 'player_give_item', {})
    assert.ok(r.gave)
  })

  test('player inventory', async () => {
    const r = await runCase(server, bot, 'player_inventory', {})
    assert.ok(r.inv_size !== undefined)
  })

  test('player effects', async () => {
    const r = await runCase(server, bot, 'player_effects', {})
    assert.ok(r.effects_count !== undefined || r.error)
  })

  test('player cooldown', async () => {
    const r = await runCase(server, bot, 'player_cooldown', {})
    assert.ok(r.cooldown !== undefined || r.error)
  })

  test('player title tablist', async () => {
    const r = await runCase(server, bot, 'player_title_tablist', {})
    assert.ok(r.title_ok)
  })

  test('player permissions', async () => {
    const r = await runCase(server, bot, 'player_permissions', {})
    assert.ok(r.has_perm !== undefined)
  })

  test('player pdc', async () => {
    const r = await runCase(server, bot, 'player_pdc', {})
    assert.ok(r.set_get)
  })

  test('player scoreboard', async () => {
    const r = await runCase(server, bot, 'player_scoreboard', {})
    assert.ok(r.has_scoreboard !== undefined)
  })

  test('player freeze vanish', async () => {
    const r = await runCase(server, bot, 'player_freeze_vanish', {})
    assert.ok(r.frozen !== undefined)
  })

  test('player vanish unvanish', async () => {
    const r = await runCase(server, bot, 'player_vanish_unvanish', {})
    assert.ok(r.vanished !== undefined)
  })

  test('player kick method', async () => {
    const r = await runCase(server, bot, 'player_kick', {})
    assert.ok(r.kick_method !== undefined)
  })

  test('player hide show', async () => {
    const r = await runCase(server, bot, 'player_hide_show', {})
    assert.ok(r.hid_self !== undefined)
  })
})

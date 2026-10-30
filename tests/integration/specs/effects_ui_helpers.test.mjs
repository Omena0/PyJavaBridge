import { test, describe } from 'node:test'
import assert from 'node:assert/strict'
import { getServer } from '../lib/server.mjs'
import { connectBot, runCase, closeBot } from '../lib/bot.mjs'

describe('Effects UI Helpers API', () => {
  let server, bot

  test.before(async () => {
    server = await getServer()
    bot = await connectBot(server)
  })

  test.after(async () => {
    await closeBot(bot)
    await server.stop()
  })

  test('effect potion', async () => {
    const r = await runCase(server, bot, 'effect_potion', {})
    assert.ok(r.applied)
  })

  test('attribute', async () => {
    const r = await runCase(server, bot, 'attribute', {})
    assert.ok(r.applied)
  })

  test('textcomponent', async () => {
    const r = await runCase(server, bot, 'textcomponent', {})
    assert.ok(r.str)
  })

  test('bookbuilder', async () => {
    const r = await runCase(server, bot, 'bookbuilder', {})
    assert.ok(r.built)
  })

  test('firework', async () => {
    const r = await runCase(server, bot, 'firework', {})
    assert.ok(r.firework_class)
  })

  test('bossbar ui', async () => {
    const r = await runCase(server, bot, 'bossbar_ui', {})
    assert.ok(r.bossbar_ok)
  })

  test('scoreboard objective team', async () => {
    const r = await runCase(server, bot, 'scoreboard_objective_team', {})
    assert.ok(r.scoreboard_ok)
  })

  test('sidebar', async () => {
    const r = await runCase(server, bot, 'sidebar', {})
    assert.ok(r.sidebar_ok)
  })

  test('menu', async () => {
    const r = await runCase(server, bot, 'menu', {})
    assert.ok(r.menu_ok)
  })

  test('actionbar display', async () => {
    const r = await runCase(server, bot, 'actionbar_display', {})
    assert.ok(r.actionbar_ok)
  })

  test('hologram', async () => {
    const r = await runCase(server, bot, 'hologram', {})
    assert.ok(r.hologram_ok)
  })

  test('display entities', async () => {
    const r = await runCase(server, bot, 'display_entities', {})
    assert.ok(r.block_display || r.block_display_error || r.item_display)
  })

  test('config state cooldown', async () => {
    const r = await runCase(server, bot, 'config_state_cooldown', {})
    assert.ok(r.cooldown_ok !== undefined || r.config || r.state)
  })

  test('paginator', async () => {
    const r = await runCase(server, bot, 'paginator', {})
    assert.ok(r.pages >= 0)
  })

  test('raycast', async () => {
    const r = await runCase(server, bot, 'raycast', {})
    assert.ok(r.has_result !== undefined)
  })

  test('enums', async () => {
    const r = await runCase(server, bot, 'enums', {})
    assert.ok(r.material_diamond)
  })

  test('datapack', async () => {
    const r = await runCase(server, bot, 'datapack', {})
    assert.ok(r.has_datapack)
  })

  test('script messaging', async () => {
    const r = await runCase(server, bot, 'script_messaging', {})
    assert.ok(r.has_script_send)
  })

  test('event fire', async () => {
    const r = await runCase(server, bot, 'event_fire', {})
    assert.ok(r.fired)
  })
})

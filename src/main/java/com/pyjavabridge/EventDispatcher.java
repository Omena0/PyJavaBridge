package com.pyjavabridge;

import com.pyjavabridge.event.CancelMode;
import com.pyjavabridge.event.PendingEvent;

import com.google.gson.Gson;
import com.google.gson.JsonElement;
import com.google.gson.JsonObject;
import net.kyori.adventure.text.Component;
import net.kyori.adventure.text.serializer.plain.PlainTextComponentSerializer;
import org.bukkit.Bukkit;
import org.bukkit.event.Event;
import org.bukkit.event.block.BlockExplodeEvent;
import org.bukkit.event.entity.EntityDamageEvent;
import org.bukkit.event.entity.EntityExplodeEvent;
import org.bukkit.event.inventory.InventoryClickEvent;
import org.bukkit.inventory.InventoryView;

import java.lang.reflect.Method;
import java.util.ArrayList;
import java.util.List;
import java.util.Map;
import java.util.function.Consumer;

public class EventDispatcher {
    private final PyJavaBridgePlugin plugin;
    private final BridgeSerializer serializer;
    private final String name;
    private final Map<Integer, PendingEvent> pendingEvents;
    private final Consumer<JsonObject> sender;
    private final Gson gson;

    EventDispatcher(PyJavaBridgePlugin plugin, BridgeSerializer serializer, String name,
                    Map<Integer, PendingEvent> pendingEvents, Consumer<JsonObject> sender, Gson gson) {
        this.plugin = plugin;
        this.serializer = serializer;
        this.name = name;
        this.pendingEvents = pendingEvents;
        this.sender = sender;
        this.gson = gson;
    }

    public void sendEvent(String eventName, JsonObject payload) {
        JsonObject message = new JsonObject();
        message.addProperty("type", "event");
        message.addProperty("event", eventName);
        message.add("payload", payload);
        sender.accept(message);
    }

    public void sendEvent(Event event, String eventName) {
        if (eventName.equalsIgnoreCase("block_explode")) {
            if (event instanceof BlockExplodeEvent blockExplodeEvent) {
                handleBlockExplode(blockExplodeEvent.blockList(), event, eventName);
                return;
            }
            if (event instanceof EntityExplodeEvent entityExplodeEvent) {
                handleBlockExplode(entityExplodeEvent.blockList(), event, eventName);
                return;
            }
            return;
        }
        if (event instanceof EntityExplodeEvent && eventName.equalsIgnoreCase("entity_explode")) {
            JsonObject payload = baseEventPayload(event, eventName);
            dispatchCancellableEvent(event, eventName, payload, CancelMode.EVENT, 1000);
            return;
        }

        JsonObject payload = baseEventPayload(event, eventName);
        dispatchCancellableEvent(event, eventName, payload, CancelMode.EVENT, 1000);
    }

    private JsonObject baseEventPayload(Event event, String eventName) {
        JsonObject payload = new JsonObject();
        payload.add("event", serializer.serialize(event));
        tryAddPayload(payload, event, "player", "getPlayer", "getWhoClicked");
        tryAddPayload(payload, event, "block", "getBlock", "getClickedBlock");
        tryAddPayload(payload, event, "entity", "getEntity");
        tryAddPayload(payload, event, "damager", "getDamager");
        if (event instanceof EntityDamageEvent damageEvent) {
            payload.addProperty("damage", damageEvent.getDamage());
            payload.addProperty("final_damage", damageEvent.getFinalDamage());
            payload.add("damage_cause", serializer.serialize(damageEvent.getCause()));
        }
        tryAddPayload(payload, event, "location", "getLocation");
        tryAddPayload(payload, event, "world", "getWorld");
        tryAddPayload(payload, event, "item", "getItem");
        tryAddPayload(payload, event, "inventory", "getInventory");
        tryAddPayload(payload, event, "chunk", "getChunk");
        if (event instanceof InventoryClickEvent clickEvent) {
            InventoryView view = clickEvent.getView();
            String title = view != null ? getInventoryViewTitle(view) : "";
            org.bukkit.inventory.Inventory inventory = clickEvent.getClickedInventory();
            if (inventory == null && view != null) {
                inventory = view.getTopInventory();
            }
            if (inventory != null) {
                payload.add("inventory", serializeInventoryWithTitle(inventory, title));
            }
            payload.addProperty("slot", clickEvent.getSlot());
            payload.add("item", serializer.serialize(clickEvent.getCurrentItem()));
        }
        return payload;
    }

    private boolean dispatchCancellableEvent(Event event, String eventName, JsonObject payload,
            CancelMode cancelMode, long timeoutMs) {
        boolean cancellable = event instanceof org.bukkit.event.Cancellable;
        int eventId = -1;
        if (cancellable) {
            eventId = plugin.nextEventId();
            payload.addProperty("id", eventId);
            PendingEvent pending = new PendingEvent();
            pending.cancellable = (org.bukkit.event.Cancellable) event;
            pending.event = event;
            pending.id = eventId;
            pendingEvents.put(eventId, pending);
        }
        sendEvent(eventName, payload);
        if (!cancellable) {
            return false;
        }
        PendingEvent pending = pendingEvents.get(eventId);
        if (pending != null) {
            long deadline = System.currentTimeMillis() + timeoutMs;
            try {
                while (System.currentTimeMillis() < deadline && pending.latch.getCount() > 0) {
                    plugin.drainMainThreadQueue();
                    pending.latch.await(5, java.util.concurrent.TimeUnit.MILLISECONDS);
                }
            } catch (InterruptedException ignored) {
                Thread.currentThread().interrupt();
            }
            boolean cancelRequested = pending.cancelRequested.get();
            if (pending.chatOverride != null && isChatEvent(pending.event)) {
                pending.cancellable.setCancelled(true);
                String message = pending.chatOverride;
                Bukkit.getScheduler().runTask(plugin,
                        () -> Bukkit.getServer().broadcast(net.kyori.adventure.text.Component.text(message)));
            }
            if (pending.damageOverride != null && pending.event instanceof EntityDamageEvent damageEvent) {
                damageEvent.setDamage(pending.damageOverride);
            }
            if (cancelRequested && cancelMode == CancelMode.EVENT) {
                pending.cancellable.setCancelled(true);
            }
            if (pending.latch.getCount() > 0 && timeoutMs >= 100) {
                plugin.getLogger().warning("[" + name + "] Event handler timed out for " + eventName);
            }
            pendingEvents.remove(eventId);
        }
        return cancellable && ((org.bukkit.event.Cancellable) event).isCancelled();
    }

    @SuppressWarnings("deprecation")
    private boolean isChatEvent(Event event) {
        return event instanceof org.bukkit.event.player.AsyncPlayerChatEvent
                || event instanceof org.bukkit.event.player.PlayerChatEvent
                || event instanceof io.papermc.paper.event.player.AsyncChatEvent;
    }

    private void handleBlockExplode(List<org.bukkit.block.Block> blocks, Event event, String eventName) {
        if (blocks.isEmpty()) {
            return;
        }
        List<PendingEvent> batch = new ArrayList<>();
        List<JsonObject> payloads = new ArrayList<>();
        for (org.bukkit.block.Block block : blocks) {
            JsonObject payload = baseEventPayload(event, eventName);
            int eventId = plugin.nextEventId();
            payload.addProperty("id", eventId);
            payload.add("block", serializer.serialize(block));
            PendingEvent pending = new PendingEvent();
            pending.block = block;
            pending.id = eventId;
            pendingEvents.put(eventId, pending);
            batch.add(pending);
            payloads.add(payload);
        }
        sendBatch(eventName, payloads);
        long deadline = System.currentTimeMillis() + 100;
        try {
            while (System.currentTimeMillis() < deadline) {
                boolean allDone = true;
                for (PendingEvent pending : batch) {
                    if (pending.latch.getCount() > 0) {
                        allDone = false;
                        break;
                    }
                }
                if (allDone) {
                    break;
                }
                plugin.drainMainThreadQueue();
                Thread.sleep(2);
            }
        } catch (InterruptedException ignored) {
            Thread.currentThread().interrupt();
        }
        java.util.Iterator<org.bukkit.block.Block> iterator = blocks.iterator();
        while (iterator.hasNext()) {
            org.bukkit.block.Block block = iterator.next();
            boolean cancel = false;
            for (PendingEvent pending : batch) {
                if (pending.block == block) {
                    cancel = pending.cancelRequested.get();
                    break;
                }
            }
            if (cancel) {
                iterator.remove();
            }
        }
        for (PendingEvent pending : batch) {
            pendingEvents.remove(pending.id);
        }
    }

    private void sendBatch(String eventName, List<JsonObject> payloads) {
        JsonObject message = new JsonObject();
        message.addProperty("type", "event_batch");
        message.addProperty("event", eventName);
        message.add("payloads", gson.toJsonTree(payloads));
        sender.accept(message);
    }

    private void tryAddPayload(JsonObject payload, Event event, String key, String... methodNames) {
        for (String methodName : methodNames) {
            try {
                Method method = event.getClass().getMethod(methodName);
                Object value = method.invoke(event);
                if (value != null) {
                    payload.add(key, serializer.serialize(value));
                    return;
                }
            } catch (Exception ignored) {
            }
        }
    }

    private JsonElement serializeInventoryWithTitle(org.bukkit.inventory.Inventory inventory, String title) {
        JsonElement element = serializer.serialize(inventory);

        if (element != null && element.isJsonObject()) {
            JsonObject obj = element.getAsJsonObject();
            JsonObject fields = obj.has("fields") && obj.get("fields").isJsonObject()
                    ? obj.getAsJsonObject("fields")
                    : new JsonObject();

            fields.addProperty("title", title != null ? title : "");
            obj.add("fields", fields);
        }
        return element;
    }

    private String getInventoryViewTitle(InventoryView view) {
        if (view == null) {
            return "";
        }

        try {
            Component component = view.title();
            if (component != null) {
                return PlainTextComponentSerializer.plainText().serialize(component);
            }

        } catch (Exception ignored) {
        }

        try {
            Method getTitle = view.getClass().getMethod("getTitle");
            Object result = getTitle.invoke(view);
            if (result != null) {
                return result.toString();
            }

        } catch (Exception ignored) {
        }
        return "";
    }
}

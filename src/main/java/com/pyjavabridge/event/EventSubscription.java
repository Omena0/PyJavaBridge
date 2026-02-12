package com.pyjavabridge.event;

import com.pyjavabridge.PyJavaBridgePlugin;
import com.pyjavabridge.BridgeInstance;

import org.bukkit.Bukkit;
import org.bukkit.event.Event;
import org.bukkit.event.EventPriority;
import org.bukkit.event.HandlerList;
import org.bukkit.event.Listener;
import org.bukkit.plugin.EventExecutor;

public class EventSubscription implements Listener {
    private final PyJavaBridgePlugin pluginRef;
    private final Class<? extends Event> eventClass;
    private final EventPriority priority;
    private long lastTick = -1;
    private long lastDispatchNano = 0;
    private final EventExecutor executor;

    public EventSubscription(PyJavaBridgePlugin plugin, BridgeInstance instance, String eventName,
            boolean oncePerTick, EventPriority priority, long throttleMs)
            throws ClassNotFoundException {
        this(plugin, instance, eventName, oncePerTick, priority, throttleMs, null);
    }

    public EventSubscription(PyJavaBridgePlugin plugin, BridgeInstance instance, String eventName,
            boolean oncePerTick, EventPriority priority, long throttleMs, Class<? extends Event> overrideClass)
            throws ClassNotFoundException {
        this.pluginRef = plugin;
        this.eventClass = overrideClass != null ? overrideClass : resolveEventClass(eventName);
        this.priority = priority != null ? priority : EventPriority.NORMAL;
        final BridgeInstance instanceRef = instance;
        final String eventNameRef = eventName;
        final boolean oncePerTickRef = oncePerTick;
        final long throttleMsRef = throttleMs;
        this.executor = (listener, event) -> {
            if (!eventClass.isInstance(event)) {
                return;
            }
            if (oncePerTickRef) {
                long tick = pluginRef.getCurrentTick();
                if (tick == lastTick) {
                    return;
                }
                lastTick = tick;
            }
            if (throttleMsRef > 0) {
                long now = System.nanoTime();
                if (now - lastDispatchNano < throttleMsRef * 1_000_000L) {
                    return;
                }
                lastDispatchNano = now;
            }
            instanceRef.sendEvent(event, eventNameRef);
        };
    }

    public void register() {
        Bukkit.getPluginManager().registerEvent(eventClass, this, this.priority, executor, pluginRef, true);
    }

    public void unregister() {
        HandlerList.unregisterAll(this);
    }

    static Class<? extends Event> resolveEventClass(String eventName) throws ClassNotFoundException {
        if (eventName.equalsIgnoreCase("server_boot")) {
            return org.bukkit.event.server.ServerLoadEvent.class;
        }
        String pascal = toPascalCase(eventName) + "Event";
        String[] packages = new String[] {
                "org.bukkit.event.player.",
                "org.bukkit.event.block.",
                "org.bukkit.event.entity.",
                "org.bukkit.event.inventory.",
                "org.bukkit.event.server.",
                "org.bukkit.event.world.",
                "org.bukkit.event.weather.",
                "org.bukkit.event.vehicle.",
                "org.bukkit.event.hanging.",
                "org.bukkit.event.enchantment.",
                "org.bukkit.event.",
                "io.papermc.paper.event.player.",
                "io.papermc.paper.event.block.",
                "io.papermc.paper.event.entity.",
                "io.papermc.paper.event.world.",
                "io.papermc.paper.event.",
        };
        for (String pkg : packages) {
            try {
                Class<?> clazz = Class.forName(pkg + pascal);
                if (Event.class.isAssignableFrom(clazz)) {
                    @SuppressWarnings("unchecked")
                    Class<? extends Event> eventClass = (Class<? extends Event>) clazz;
                    return eventClass;
                }
            } catch (ClassNotFoundException ignored) {
            }
        }
        throw new ClassNotFoundException("Event not found for " + eventName);
    }

    static String toPascalCase(String value) {
        StringBuilder builder = new StringBuilder();
        for (String part : value.split("_")) {
            if (part.isEmpty()) {
                continue;
            }
            builder.append(part.substring(0, 1).toUpperCase()).append(part.substring(1));
        }
        return builder.toString();
    }
}

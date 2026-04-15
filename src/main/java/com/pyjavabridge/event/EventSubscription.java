package com.pyjavabridge.event;

import com.pyjavabridge.PyJavaBridgePlugin;
import com.pyjavabridge.BridgeInstance;

import org.bukkit.event.Event;
import org.bukkit.event.EventPriority;
import org.bukkit.event.HandlerList;
import org.bukkit.event.Listener;
import org.bukkit.plugin.EventExecutor;
import org.bukkit.plugin.RegisteredListener;

import java.lang.reflect.Method;
import java.util.concurrent.ConcurrentHashMap;
import java.util.concurrent.atomic.AtomicLong;

public class EventSubscription implements Listener {
    // Cache resolved event classes to avoid repeated Class.forName() across 13 packages
    private static final ConcurrentHashMap<String, Class<? extends Event>> eventClassCache = new ConcurrentHashMap<>();

    private final PyJavaBridgePlugin pluginRef;
    private final Class<?> eventClass;
    private final EventPriority priority;
    private final AtomicLong lastTick = new AtomicLong(-1);
    private volatile long lastDispatchNano = 0;
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
            if (!instanceRef.isRunning()) {
                return;
            }
            if (oncePerTickRef) {
                long tick = pluginRef.getCurrentTick();
                long previous = lastTick.getAndSet(tick);
                if (tick == previous) {
                    return;
                }
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
        // Do not ignore cancelled events: some events (e.g. interact air) are pre-cancelled by Bukkit.
        HandlerList handlerList = resolveHandlerList(this.eventClass);
        RegisteredListener listener = new RegisteredListener(this, this.executor, this.priority, this.pluginRef, false);
        handlerList.register(listener);
    }

    public void unregister() {
        HandlerList.unregisterAll(this);
    }

    static Class<? extends Event> resolveEventClass(String eventName) throws ClassNotFoundException {
        Class<? extends Event> cached = eventClassCache.get(eventName);
        if (cached != null) return cached;

        if (eventName.equalsIgnoreCase("server_boot")) {
            eventClassCache.put(eventName, org.bukkit.event.server.ServerLoadEvent.class);
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
                    eventClassCache.put(eventName, eventClass);
                    return eventClass;
                }
            } catch (ClassNotFoundException ignored) {
            }
        }
        throw new ClassNotFoundException("Event not found for " + eventName);
    }

    private static HandlerList resolveHandlerList(Class<?> type) {
        if (!Event.class.isAssignableFrom(type)) {
            throw new IllegalStateException("Type is not a Bukkit event: " + type.getName());
        }

        try {
            Method method = type.getMethod("getHandlerList");
            Object value = method.invoke(null);
            if (value instanceof HandlerList) {
                return (HandlerList) value;
            }
        } catch (ReflectiveOperationException ex) {
            throw new IllegalStateException("Unable to resolve handler list for event type: " + type.getName(), ex);
        }

        throw new IllegalStateException("Event type does not expose static getHandlerList(): " + type.getName());
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

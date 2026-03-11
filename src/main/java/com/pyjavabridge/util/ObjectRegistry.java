package com.pyjavabridge.util;

import java.util.Collection;
import java.util.IdentityHashMap;
import java.util.Map;
import java.util.concurrent.ConcurrentHashMap;
import java.util.concurrent.atomic.AtomicInteger;
import java.util.concurrent.locks.StampedLock;

/**
 * Thread-safe registry that maps Java objects to integer handles for
 * referencing across the Python bridge. Uses ConcurrentHashMap for
 * lock-free reads and a StampedLock-guarded IdentityHashMap for
 * reverse lookups (object → handle).
 */
public class ObjectRegistry {
    private final Map<Integer, Object> objects = new ConcurrentHashMap<>();
    private final IdentityHashMap<Object, Integer> reverseMap = new IdentityHashMap<>();
    // StampedLock for read-heavy access (get() is lock-free via ConcurrentHashMap,
    //      register/release use write lock on reverseMap)
    private final StampedLock reverseLock = new StampedLock();
    private final AtomicInteger counter = new AtomicInteger(1);

    /** Registers an object and returns its integer handle. Returns an existing handle if already registered. */
    public int register(Object obj) {
        if (obj == null) {
            return 0;
        }
        long stamp = reverseLock.writeLock();
        try {
            Integer existing = reverseMap.get(obj);
            if (existing != null && objects.containsKey(existing)) {
                return existing;
            }
            int id = counter.getAndIncrement();
            objects.put(id, obj);
            reverseMap.put(obj, id);
            return id;
        } finally {
            reverseLock.unlockWrite(stamp);
        }
    }

    public Object get(int id) {
        return objects.get(id);
    }

    public void release(int id) {
        long stamp = reverseLock.writeLock();
        try {
            Object removed = objects.remove(id);
            if (removed != null) {
                reverseMap.remove(removed);
            }
        } finally {
            reverseLock.unlockWrite(stamp);
        }
    }

    public void releaseAll(Collection<Integer> ids) {
        long stamp = reverseLock.writeLock();
        try {
            for (int id : ids) {
                Object removed = objects.remove(id);
                if (removed != null) {
                    reverseMap.remove(removed);
                }
            }
        } finally {
            reverseLock.unlockWrite(stamp);
        }
    }

    public Collection<Object> getAll() {
        return objects.values();
    }
}

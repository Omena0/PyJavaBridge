package com.pyjavabridge.util;

import java.util.Collection;
import java.util.IdentityHashMap;
import java.util.Map;
import java.util.concurrent.ConcurrentHashMap;
import java.util.concurrent.atomic.AtomicInteger;

public class ObjectRegistry {
    private final Map<Integer, Object> objects = new ConcurrentHashMap<>();
    private final IdentityHashMap<Object, Integer> reverseMap = new IdentityHashMap<>();
    private final Object reverseLock = new Object();
    private final AtomicInteger counter = new AtomicInteger(1);

    public int register(Object obj) {
        if (obj == null) {
            return 0;
        }
        synchronized (reverseLock) {
            Integer existing = reverseMap.get(obj);
            if (existing != null && objects.containsKey(existing)) {
                return existing;
            }
            int id = counter.getAndIncrement();
            objects.put(id, obj);
            reverseMap.put(obj, id);
            return id;
        }
    }

    public Object get(int id) {
        return objects.get(id);
    }

    public void release(int id) {
        Object removed = objects.remove(id);
        if (removed != null) {
            synchronized (reverseLock) {
                reverseMap.remove(removed);
            }
        }
    }

    public void releaseAll(Collection<Integer> ids) {
        for (int id : ids) {
            release(id);
        }
    }
}

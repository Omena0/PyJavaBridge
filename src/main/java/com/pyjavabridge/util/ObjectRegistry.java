package com.pyjavabridge.util;

import java.util.Collection;
import java.util.Map;
import java.util.concurrent.ConcurrentHashMap;
import java.util.concurrent.atomic.AtomicInteger;

public class ObjectRegistry {
    private final Map<Integer, Object> objects = new ConcurrentHashMap<>();
    private final AtomicInteger counter = new AtomicInteger(1);

    public int register(Object obj) {
        if (obj == null) {
            return 0;
        }
        int id = counter.getAndIncrement();
        objects.put(id, obj);
        return id;
    }

    public Object get(int id) {
        return objects.get(id);
    }

    public void release(int id) {
        objects.remove(id);
    }

    public void releaseAll(Collection<Integer> ids) {
        for (int id : ids) {
            objects.remove(id);
        }
    }
}

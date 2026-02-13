package com.pyjavabridge.facade;

import com.pyjavabridge.BridgeInstance;
import com.pyjavabridge.util.EntityGoneException;
import com.pyjavabridge.util.EnumValue;

import com.google.gson.JsonObject;

import org.bukkit.World;
import org.bukkit.block.Block;
import org.bukkit.block.BlockState;
import org.bukkit.entity.EntityType;
import org.bukkit.inventory.InventoryHolder;

import java.lang.reflect.InvocationTargetException;
import java.lang.reflect.Method;
import java.util.Collections;
import java.util.List;
import java.util.Map;
import java.util.UUID;

public class RefFacade {
    private final BridgeInstance instance;

    public RefFacade(BridgeInstance instance) {
        this.instance = instance;
    }

    public Object call(String refType, String refId, String method, List<Object> args) throws Exception {
        return call(refType, refId, method, args, null);
    }

    public Object call(String refType, String refId, String method, List<Object> args, JsonObject kwargs) throws Exception {
        if ("player_name".equalsIgnoreCase(refType) && "getUniqueId".equals(method)) {
            UUID uuid = instance.getPlugin().resolvePlayerUuidByName(refId);
            if (uuid != null) {
                return uuid;
            }
            throw new EntityGoneException("player_name not found: " + refId);
        }
        Object target = instance.resolveRef(refType, refId);
        if (target == null) {
            throw new EntityGoneException(refType + " not found: " + refId);
        }
        if (target instanceof org.bukkit.entity.Player player && !player.isOnline()) {
            throw new EntityGoneException("Player is no longer online");
        }
        if (target instanceof org.bukkit.entity.Entity entity) {
            if (entity.isDead()) {
                throw new EntityGoneException("Entity is no longer valid");
            }
            if (!entity.isValid() && !(entity instanceof org.bukkit.entity.Display)) {
                throw new EntityGoneException("Entity is no longer valid");
            }
        }
        if (target instanceof Block blockTarget && "getInventory".equals(method)) {
            BlockState state = blockTarget.getState();
            if (state instanceof InventoryHolder holder) {
                return holder.getInventory();
            }
            return null;
        }
        if ("getUniqueId".equals(method) && target instanceof org.bukkit.entity.Entity entity) {
            return entity.getUniqueId();
        }
        if (target instanceof org.bukkit.entity.Player playerTarget && "kick".equals(method)) {
            return instance.handleKick(playerTarget, args);
        }
        if (target instanceof World worldTarget && args.size() == 2 && ("spawnEntity".equals(method) || "spawn".equals(method))) {
            Object locationObj = args.get(0);
            Object typeObj = args.get(1);

            if ("spawn".equals(method)) {
                if (!(typeObj instanceof EnumValue) && !(typeObj instanceof String) && !(typeObj instanceof EntityType)) {
                    typeObj = null;
                }
            }

            if (typeObj == null && "spawn".equals(method)) {
                // fall through to reflection
            } else {
                Map<String, Object> options = kwargs == null ? Collections.emptyMap() : instance.deserializeArgsObject(kwargs);
                return instance.spawnEntityWithOptions(worldTarget, locationObj, typeObj, options);
            }
        }
        if (target instanceof World worldTarget && "spawnImagePixels".equals(method) && args.size() >= 2) {
            Object locationObj = args.get(0);
            Object pixelsObj = args.get(1);
            return instance.spawnImagePixels(worldTarget, locationObj, pixelsObj);
        }
        Method[] methods = target.getClass().getMethods();
        for (Method candidate : methods) {
            if (!candidate.getName().equals(method)) {
                continue;
            }
            if (candidate.getParameterCount() != args.size()) {
                continue;
            }
            Object[] converted = instance.convertArgs(candidate.getParameterTypes(), args);
            if (converted != null) {
                try {
                    return candidate.invoke(target, converted);
                } catch (InvocationTargetException ex) {
                    Throwable cause = ex.getCause();
                    if (cause instanceof Exception exception) {
                        throw exception;
                    }
                    throw ex;
                }
            }
        }
        throw new NoSuchMethodException("Method not found: " + method + " on " + target.getClass().getName());
    }

    public Object getAttr(String refType, String refId, String field) throws Exception {
        Object target = instance.resolveRef(refType, refId);
        if (target == null) {
            throw new EntityGoneException(refType + " not found: " + refId);
        }
        return instance.getField(target, field);
    }

    public void setAttr(String refType, String refId, String field, Object value) throws Exception {
        Object target = instance.resolveRef(refType, refId);
        if (target == null) {
            throw new EntityGoneException(refType + " not found: " + refId);
        }
        instance.setField(target, field, value);
    }
}

package com.pyjavabridge.util;

import com.google.gson.JsonObject;

import net.kyori.adventure.text.Component;
import org.bukkit.Color;
import org.bukkit.Location;
import org.bukkit.World;
import org.bukkit.entity.Display;
import org.bukkit.entity.Entity;
import org.bukkit.entity.EntityType;
import org.bukkit.entity.LivingEntity;
import org.bukkit.entity.TextDisplay;
import org.bukkit.event.entity.CreatureSpawnEvent;
import org.bukkit.util.Transformation;
import org.bukkit.util.Vector;
import org.joml.Quaternionf;
import org.joml.Vector3f;

import java.lang.reflect.Method;
import java.util.ArrayList;
import java.util.Collections;
import java.util.EnumMap;
import java.util.List;
import java.util.Map;
import java.util.logging.Logger;

public class EntitySpawner {
    private final Logger logger;
    private final String name;

    private static final Map<EntityType, NonLivingSpawner> NON_LIVING_SPAWNERS = new EnumMap<>(EntityType.class);

    static {
        for (EntityType type : EntityType.values()) {
            Class<?> entityClass = type.getEntityClass();
            if (entityClass != null && !LivingEntity.class.isAssignableFrom(entityClass)) {
                NON_LIVING_SPAWNERS.put(type,
                        (world, location, entityType) -> spawnNonLivingEntity(world, location, entityType));
            }
        }
    }

    public EntitySpawner(Logger logger, String name) {
        this.logger = logger;
        this.name = name;
    }

    public Entity spawnEntityWithOptions(World worldTarget, Object locationObj, Object typeObj,
            Map<String, Object> options) throws Exception {
        Location location = resolveSpawnLocation(worldTarget, locationObj, options);
        EntityType entityType = resolveEntityType(typeObj);

        if (entityType == null) {
            throw new IllegalArgumentException("spawnEntity requires a valid EntityType");
        }

        Class<? extends Entity> entityClass = entityType.getEntityClass();
        Entity spawned;

        if (entityClass != null && LivingEntity.class.isAssignableFrom(entityClass)) {
            @SuppressWarnings("unchecked")
            Class<? extends LivingEntity> livingClass = (Class<? extends LivingEntity>) entityClass;
            spawned = worldTarget.spawn(location, livingClass, CreatureSpawnEvent.SpawnReason.CUSTOM, true, entity -> {
            });

        } else {
            NonLivingSpawner nonLivingSpawner = NON_LIVING_SPAWNERS.get(entityType);

            if (nonLivingSpawner == null) {
                throw new IllegalArgumentException("spawnEntity could not spawn entity type: " + entityType.name());
            }

            spawned = nonLivingSpawner.spawn(worldTarget, location, entityType);
        }

        if (spawned == null) {
            throw new IllegalArgumentException("spawnEntity could not spawn entity type: " + entityType.name());
        }

        applySpawnOptions(spawned, location, options);
        return spawned;
    }

    @SuppressWarnings("unchecked")
    public List<Entity> spawnImagePixels(World worldTarget, Object locationObj, Object pixelsObj) throws Exception {
        Location baseLocation = resolveSpawnLocation(worldTarget, locationObj, Collections.emptyMap());
        if (baseLocation == null) {
            throw new IllegalArgumentException("spawnImagePixels requires a valid location");
        }

        if (!(pixelsObj instanceof List<?> pixelEntries)) {
            throw new IllegalArgumentException("spawnImagePixels requires a list payload");
        }

        List<Entity> spawned = new ArrayList<>();
        int spawnedViaWorldSpawn = 0;
        int skippedEntries = 0;
        int worldSpawnErrors = 0;
        int nullAfterSpawn = 0;
        String worldSpawnLastError = null;
        logger.info("[" + name + "] spawnImagePixels payload entries: " + pixelEntries.size());

        int baseChunkX = baseLocation.getBlockX() >> 4;
        int baseChunkZ = baseLocation.getBlockZ() >> 4;
        try {
            if (!worldTarget.isChunkLoaded(baseChunkX, baseChunkZ)) {
                worldTarget.loadChunk(baseChunkX, baseChunkZ, true);
            }
        } catch (Exception ex) {
            logger.warning("[" + name + "] spawnImagePixels chunk preload failed: " + ex.getMessage());
        }

        for (Object entryObj : pixelEntries) {
            float baseXShift;
            float baseYShift;
            float xOffset;
            float yOffset;
            float zOffset;
            float baseZShift;
            float scaleX;
            float scaleY;
            float scaleZ;
            float yaw;
            float pitch;
            int lineWidth;
            int argb;

            if (entryObj instanceof JsonObject entryJson) {
                baseXShift = entryJson.has("baseXShift") ? entryJson.get("baseXShift").getAsFloat() : 0f;
                baseYShift = entryJson.has("baseYShift") ? entryJson.get("baseYShift").getAsFloat() : 0f;
                xOffset = entryJson.has("xOffset") ? entryJson.get("xOffset").getAsFloat() : 0f;
                yOffset = entryJson.has("yOffset") ? entryJson.get("yOffset").getAsFloat() : 0f;
                zOffset = entryJson.has("zOffset") ? entryJson.get("zOffset").getAsFloat() : 0f;
                baseZShift = entryJson.has("baseZShift") ? entryJson.get("baseZShift").getAsFloat() : 0f;

                scaleX = entryJson.has("scaleX") ? entryJson.get("scaleX").getAsFloat() : 1f;
                scaleY = entryJson.has("scaleY") ? entryJson.get("scaleY").getAsFloat() : 1f;
                scaleZ = entryJson.has("scaleZ") ? entryJson.get("scaleZ").getAsFloat() : 1f;

                yaw = entryJson.has("yaw") ? entryJson.get("yaw").getAsFloat() : baseLocation.getYaw();
                pitch = entryJson.has("pitch") ? entryJson.get("pitch").getAsFloat() : baseLocation.getPitch();
                lineWidth = entryJson.has("lineWidth") ? entryJson.get("lineWidth").getAsInt() : 1;
                argb = entryJson.has("argb") ? entryJson.get("argb").getAsInt() : 0x00000000;

            } else if (entryObj instanceof Map<?, ?> rawMap) {
                Map<String, Object> entry = (Map<String, Object>) rawMap;

                baseXShift = entry.get("baseXShift") instanceof Number n ? n.floatValue() : 0f;
                baseYShift = entry.get("baseYShift") instanceof Number n ? n.floatValue() : 0f;
                xOffset = entry.get("xOffset") instanceof Number n ? n.floatValue() : 0f;
                yOffset = entry.get("yOffset") instanceof Number n ? n.floatValue() : 0f;
                zOffset = entry.get("zOffset") instanceof Number n ? n.floatValue() : 0f;
                baseZShift = entry.get("baseZShift") instanceof Number n ? n.floatValue() : 0f;

                scaleX = entry.get("scaleX") instanceof Number n ? n.floatValue() : 1f;
                scaleY = entry.get("scaleY") instanceof Number n ? n.floatValue() : 1f;
                scaleZ = entry.get("scaleZ") instanceof Number n ? n.floatValue() : 1f;

                yaw = entry.get("yaw") instanceof Number n ? n.floatValue() : baseLocation.getYaw();
                pitch = entry.get("pitch") instanceof Number n ? n.floatValue() : baseLocation.getPitch();
                lineWidth = entry.get("lineWidth") instanceof Number n ? n.intValue() : 1;
                argb = entry.get("argb") instanceof Number n ? n.intValue() : 0x00000000;

            } else {
                skippedEntries++;
                continue;
            }

            Location spawnLocation = baseLocation.clone();
            spawnLocation.setX(spawnLocation.getX() + baseXShift);
            spawnLocation.setY(spawnLocation.getY() + baseYShift);
            spawnLocation.setZ(spawnLocation.getZ() + baseZShift);
            spawnLocation.setYaw(yaw);
            spawnLocation.setPitch(pitch);

            TextDisplay raw = null;
            try {
                raw = worldTarget.spawn(spawnLocation, TextDisplay.class, entity -> {
                });
                if (raw != null) {
                    spawnedViaWorldSpawn++;
                }
            } catch (Exception ex) {
                worldSpawnErrors++;
                worldSpawnLastError = ex.getClass().getSimpleName() + ": " + ex.getMessage();
            }

            if (raw == null) {
                nullAfterSpawn++;
                continue;
            }

            raw.setBillboard(Display.Billboard.FIXED);
            raw.setRotation(yaw, pitch);
            raw.setShadowed(false);
            raw.setLineWidth(lineWidth);
            raw.setDefaultBackground(false);
            raw.setBackgroundColor(Color.fromARGB(argb));
            raw.setTextOpacity((byte) 0);
            raw.text(Component.text(" "));

            Quaternionf identity = new Quaternionf(0, 0, 0, 1);
            raw.setTransformation(new Transformation(
                    new Vector3f(xOffset, yOffset, zOffset),
                    identity,
                    new Vector3f(scaleX, scaleY, scaleZ),
                    new Quaternionf(identity)));

            spawned.add(raw);
        }

        logger.info("[" + name + "] spawnImagePixels spawned " + spawned.size()
                + " entities (world.spawn=" + spawnedViaWorldSpawn + ")");
        if (spawned.isEmpty() || worldSpawnErrors > 0 || skippedEntries > 0 || nullAfterSpawn > 0) {
            logger.info("[" + name + "] spawnImagePixels diagnostics: nullAfterSpawn=" + nullAfterSpawn
                    + ", skippedEntries=" + skippedEntries
                    + ", world.spawn.errors=" + worldSpawnErrors);
            if (worldSpawnLastError != null) {
                logger.warning("[" + name + "] world.spawn last error: " + worldSpawnLastError);
            }
        }

        return spawned;
    }

    Location resolveSpawnLocation(World worldTarget, Object locationObj, Map<String, Object> options) {
        Location location = null;

        if (locationObj instanceof Location loc) {
            location = loc.clone();
        } else if (locationObj instanceof List<?> list && list.size() >= 3) {
            Double x = list.get(0) instanceof Number n ? n.doubleValue() : null;
            Double y = list.get(1) instanceof Number n ? n.doubleValue() : null;
            Double z = list.get(2) instanceof Number n ? n.doubleValue() : null;

            if (x != null && y != null && z != null) {
                float yaw = list.size() > 3 && list.get(3) instanceof Number n ? n.floatValue() : 0f;
                float pitch = list.size() > 4 && list.get(4) instanceof Number n ? n.floatValue() : 0f;
                location = new Location(worldTarget, x, y, z, yaw, pitch);
            }
        }

        if (location == null) {
            throw new IllegalArgumentException("spawnEntity requires a Location");
        }

        if (location.getWorld() == null) {
            location.setWorld(worldTarget);
        }

        Object yawObj = options.get("yaw");
        Object pitchObj = options.get("pitch");

        if (yawObj instanceof Number yaw) {
            location.setYaw(yaw.floatValue());
        }
        if (pitchObj instanceof Number pitch) {
            location.setPitch(pitch.floatValue());
        }

        Object facingObj = options.get("facing");
        Vector facing = resolveVector(facingObj);

        if (facing != null) {
            location.setDirection(facing);
        }

        return location;
    }

    private EntityType resolveEntityType(Object typeObj) {
        if (typeObj instanceof EntityType type) {
            return type;
        }
        if (typeObj instanceof EnumValue enumValue) {
            return EntityType.valueOf(enumValue.name);
        }
        if (typeObj instanceof String text) {
            return EntityType.valueOf(text);
        }
        return null;
    }

    private void applyEntityNbt(Entity entity, Object nbtObj) throws Exception {
        if (entity == null || nbtObj == null) {
            return;
        }
        if (!(nbtObj instanceof String snbt)) {
            throw new IllegalArgumentException("nbt must be an SNBT string");
        }

        Class<?> tagParserClass = Class.forName("net.minecraft.nbt.TagParser");
        Method parseTag = tagParserClass.getMethod("parseTag", String.class);
        Object compoundTag = parseTag.invoke(null, snbt);

        Method remove = compoundTag.getClass().getMethod("remove", String.class);
        remove.invoke(compoundTag, "id");

        Method getHandle = entity.getClass().getMethod("getHandle");
        Object nmsEntity = getHandle.invoke(entity);

        Method load = nmsEntity.getClass().getMethod("load", compoundTag.getClass());
        load.invoke(nmsEntity, compoundTag);
    }

    private void applySpawnOptions(Entity entity, Location location, Map<String, Object> options) throws Exception {
        if (entity == null || options == null) {
            return;
        }

        Vector velocity = resolveVector(options.get("velocity"));

        if (velocity != null) {
            entity.setVelocity(velocity);
        }

        boolean hasFacing = options.containsKey("facing");
        boolean hasYawPitch = options.get("yaw") instanceof Number || options.get("pitch") instanceof Number;

        if ((hasFacing || hasYawPitch) && location != null) {
            Location target = location.clone();

            Object yawObj = options.get("yaw");
            Object pitchObj = options.get("pitch");

            if (yawObj instanceof Number yaw) {
                target.setYaw(yaw.floatValue());
            }
            if (pitchObj instanceof Number pitch) {
                target.setPitch(pitch.floatValue());
            }

            Vector facing = resolveVector(options.get("facing"));
            if (facing != null) {
                target.setDirection(facing);
            }

            entity.teleport(target);
        }

        applyEntityNbt(entity, options.get("nbt"));
    }

    private Vector resolveVector(Object obj) {
        if (obj instanceof Vector vector) {
            return vector;
        }
        if (obj instanceof Location location) {
            return location.getDirection();
        }
        if (obj instanceof List<?> list && list.size() >= 3) {
            Double x = list.get(0) instanceof Number n ? n.doubleValue() : null;
            Double y = list.get(1) instanceof Number n ? n.doubleValue() : null;
            Double z = list.get(2) instanceof Number n ? n.doubleValue() : null;

            if (x != null && y != null && z != null) {
                return new Vector(x, y, z);
            }
        }
        if (obj instanceof Map<?, ?> map) {
            Object xObj = map.get("x");
            Object yObj = map.get("y");
            Object zObj = map.get("z");

            Double x = xObj instanceof Number n ? n.doubleValue() : null;
            Double y = yObj instanceof Number n ? n.doubleValue() : null;
            Double z = zObj instanceof Number n ? n.doubleValue() : null;

            if (x != null && y != null && z != null) {
                return new Vector(x, y, z);
            }
        }
        return null;
    }

    private static Entity spawnNonLivingEntity(World world, Location location, EntityType entityType) throws Exception {
        Object craftWorld = world;
        Class<?> craftWorldClass = craftWorld.getClass();

        Method getHandle = craftWorldClass.getMethod("getHandle");
        Object serverLevel = getHandle.invoke(craftWorld);

        Class<?> craftEntityTypeClass = Class.forName("org.bukkit.craftbukkit.entity.CraftEntityType");
        Method bukkitToMinecraft = craftEntityTypeClass.getMethod("bukkitToMinecraft", EntityType.class);
        Object nmsEntityType = bukkitToMinecraft.invoke(null, entityType);

        if (nmsEntityType == null) {
            return null;
        }

        Class<?> blockPosClass = Class.forName("net.minecraft.core.BlockPos");
        Method containing = blockPosClass.getMethod("containing", double.class, double.class, double.class);
        Object blockPos = containing.invoke(null, location.getX(), location.getY(), location.getZ());

        Class<?> spawnReasonClass = Class.forName("net.minecraft.world.entity.EntitySpawnReason");
        @SuppressWarnings({ "rawtypes", "unchecked" })
        Object spawnReason = Enum.valueOf((Class) spawnReasonClass, "COMMAND");

        Method create = nmsEntityType.getClass().getMethod(
                "create",
                Class.forName("net.minecraft.server.level.ServerLevel"),
                java.util.function.Consumer.class,
                blockPosClass,
                spawnReasonClass,
                boolean.class,
                boolean.class);

        Object nmsEntity = create.invoke(
                nmsEntityType,
                serverLevel,
                (java.util.function.Consumer<Object>) entity -> {
                },
                blockPos,
                spawnReason,
                false,
                false);

        if (nmsEntity == null) {
            return null;
        }

        Method addEntityToWorld = craftWorldClass.getMethod(
                "addEntityToWorld",
                Class.forName("net.minecraft.world.entity.Entity"),
                CreatureSpawnEvent.SpawnReason.class);

        addEntityToWorld.invoke(craftWorld, nmsEntity, CreatureSpawnEvent.SpawnReason.CUSTOM);

        Method getBukkitEntity = nmsEntity.getClass().getMethod("getBukkitEntity");
        Object bukkitEntity = getBukkitEntity.invoke(nmsEntity);

        return bukkitEntity instanceof Entity entity ? entity : null;
    }
}

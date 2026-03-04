package com.pyjavabridge.util;

import com.google.gson.JsonElement;
import com.google.gson.JsonObject;

import net.kyori.adventure.text.Component;
import org.bukkit.Color;
import org.bukkit.FireworkEffect;
import org.bukkit.Location;
import org.bukkit.World;
import org.bukkit.entity.Display;
import org.bukkit.entity.Entity;
import org.bukkit.entity.EntityType;
import org.bukkit.entity.Firework;
import org.bukkit.entity.LivingEntity;
import org.bukkit.inventory.meta.FireworkMeta;
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
    public Entity spawnFirework(World world, Object locationObj, Map<String, Object> options) throws Exception {
        Location location = resolveSpawnLocation(world, locationObj, options);
        Firework firework = world.spawn(location, Firework.class);
        FireworkMeta meta = firework.getFireworkMeta();

        int power = options.containsKey("power") ? ((Number) options.get("power")).intValue() : 1;
        meta.setPower(power);

        Object effectsObj = options.get("effects");
        if (effectsObj instanceof List<?> effectsList) {
            for (Object effectObj : effectsList) {
                if (effectObj instanceof Map<?, ?> effectMap) {
                    meta.addEffect(buildFireworkEffect((Map<String, Object>) effectMap));
                }
            }
        }

        firework.setFireworkMeta(meta);
        return firework;
    }

    @SuppressWarnings("unchecked")
    private FireworkEffect buildFireworkEffect(Map<String, Object> effectMap) {
        FireworkEffect.Builder builder = FireworkEffect.builder();

        String typeName = String.valueOf(effectMap.getOrDefault("type", "BALL")).toUpperCase();
        builder.with(FireworkEffect.Type.valueOf(typeName));

        if (effectMap.containsKey("colors")) {
            for (Object colorObj : (List<Object>) effectMap.get("colors")) {
                builder.withColor(parseColor(colorObj));
            }
        } else {
            builder.withColor(Color.WHITE);
        }

        if (effectMap.containsKey("fade_colors")) {
            for (Object colorObj : (List<Object>) effectMap.get("fade_colors")) {
                builder.withFade(parseColor(colorObj));
            }
        }

        if (effectMap.containsKey("flicker")) {
            builder.flicker((boolean) effectMap.get("flicker"));
        }
        if (effectMap.containsKey("trail")) {
            builder.trail((boolean) effectMap.get("trail"));
        }

        return builder.build();
    }

    private Color parseColor(Object colorObj) {
        if (colorObj instanceof Number num) {
            return Color.fromRGB(num.intValue());
        }
        if (colorObj instanceof String str) {
            return switch (str.toUpperCase()) {
                case "RED" -> Color.RED;
                case "BLUE" -> Color.BLUE;
                case "GREEN" -> Color.GREEN;
                case "YELLOW" -> Color.YELLOW;
                case "WHITE" -> Color.WHITE;
                case "BLACK" -> Color.BLACK;
                case "ORANGE" -> Color.ORANGE;
                case "PURPLE" -> Color.PURPLE;
                case "AQUA" -> Color.AQUA;
                case "LIME" -> Color.LIME;
                case "FUCHSIA" -> Color.FUCHSIA;
                case "SILVER" -> Color.SILVER;
                case "GRAY" -> Color.GRAY;
                case "MAROON" -> Color.MAROON;
                case "OLIVE" -> Color.OLIVE;
                case "TEAL" -> Color.TEAL;
                case "NAVY" -> Color.NAVY;
                default -> {
                    if (str.startsWith("#")) {
                        yield Color.fromRGB(Integer.parseInt(str.substring(1), 16));
                    }
                    yield Color.WHITE;
                }
            };
        }
        if (colorObj instanceof List<?> rgb && rgb.size() >= 3) {
            return Color.fromRGB(
                ((Number) rgb.get(0)).intValue(),
                ((Number) rgb.get(1)).intValue(),
                ((Number) rgb.get(2)).intValue()
            );
        }
        return Color.WHITE;
    }

    private static final int MAX_IMAGE_PIXELS = 10_000;

    @SuppressWarnings("unchecked")
    public List<Entity> spawnImagePixels(World worldTarget, Object locationObj, Object pixelsObj) throws Exception {
        Location baseLocation = resolveSpawnLocation(worldTarget, locationObj, Collections.emptyMap());
        if (baseLocation == null) {
            throw new IllegalArgumentException("spawnImagePixels requires a valid location");
        }

        if (!(pixelsObj instanceof List<?> pixelEntries)) {
            throw new IllegalArgumentException("spawnImagePixels requires a list payload");
        }

        if (pixelEntries.size() > MAX_IMAGE_PIXELS) {
            throw new IllegalArgumentException("spawnImagePixels pixel count " + pixelEntries.size()
                    + " exceeds maximum of " + MAX_IMAGE_PIXELS);
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
                JsonElement e;
                baseXShift = (e = entryJson.get("baseXShift")) != null ? e.getAsFloat() : 0f;
                baseYShift = (e = entryJson.get("baseYShift")) != null ? e.getAsFloat() : 0f;
                xOffset = (e = entryJson.get("xOffset")) != null ? e.getAsFloat() : 0f;
                yOffset = (e = entryJson.get("yOffset")) != null ? e.getAsFloat() : 0f;
                zOffset = (e = entryJson.get("zOffset")) != null ? e.getAsFloat() : 0f;
                baseZShift = (e = entryJson.get("baseZShift")) != null ? e.getAsFloat() : 0f;

                scaleX = (e = entryJson.get("scaleX")) != null ? e.getAsFloat() : 1f;
                scaleY = (e = entryJson.get("scaleY")) != null ? e.getAsFloat() : 1f;
                scaleZ = (e = entryJson.get("scaleZ")) != null ? e.getAsFloat() : 1f;

                yaw = (e = entryJson.get("yaw")) != null ? e.getAsFloat() : baseLocation.getYaw();
                pitch = (e = entryJson.get("pitch")) != null ? e.getAsFloat() : baseLocation.getPitch();
                lineWidth = (e = entryJson.get("lineWidth")) != null ? e.getAsInt() : 1;
                argb = (e = entryJson.get("argb")) != null ? e.getAsInt() : 0x00000000;

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

    // #14: Cached NMS reflection handles
    private static volatile Method cachedParseTag;
    private static volatile Method cachedGetHandle;

    private void applyEntityNbt(Entity entity, Object nbtObj) throws Exception {
        if (entity == null || nbtObj == null) {
            return;
        }
        if (!(nbtObj instanceof String snbt)) {
            throw new IllegalArgumentException("nbt must be an SNBT string");
        }

        Method parseTag = cachedParseTag;
        if (parseTag == null) {
            Class<?> tagParserClass = Class.forName("net.minecraft.nbt.TagParser");
            parseTag = tagParserClass.getMethod("parseTag", String.class);
            cachedParseTag = parseTag;
        }
        Object compoundTag = parseTag.invoke(null, snbt);

        Method remove = compoundTag.getClass().getMethod("remove", String.class);
        remove.invoke(compoundTag, "id");

        Method getHandle = cachedGetHandle;
        if (getHandle == null || getHandle.getDeclaringClass() != entity.getClass()) {
            getHandle = entity.getClass().getMethod("getHandle");
            cachedGetHandle = getHandle;
        }
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
        // Use Bukkit API — works on all Paper 1.21+ versions without NMS
        try {
            return world.spawnEntity(location, entityType);
        } catch (Exception ignored) {
        }

        // NMS fallback with multi-version support
        return spawnNonLivingNms(world, location, entityType);
    }

    // #14: Cached NMS reflection handles for spawnNonLivingNms
    private static volatile Method cachedCraftWorldGetHandle;
    private static volatile Method cachedBukkitToMinecraft;
    private static volatile Method cachedBlockPosContaining;
    private static volatile Class<?> cachedServerLevelClass;
    private static volatile Class<?> cachedNmsEntityClass;

    private static Entity spawnNonLivingNms(World world, Location location, EntityType entityType) throws Exception {
        Object craftWorld = world;
        Class<?> craftWorldClass = craftWorld.getClass();

        Method getHandle = cachedCraftWorldGetHandle;
        if (getHandle == null) {
            getHandle = craftWorldClass.getMethod("getHandle");
            cachedCraftWorldGetHandle = getHandle;
        }
        Object serverLevel = getHandle.invoke(craftWorld);

        Method bukkitToMinecraft = cachedBukkitToMinecraft;
        if (bukkitToMinecraft == null) {
            Class<?> craftEntityTypeClass = Class.forName("org.bukkit.craftbukkit.entity.CraftEntityType");
            bukkitToMinecraft = craftEntityTypeClass.getMethod("bukkitToMinecraft", EntityType.class);
            cachedBukkitToMinecraft = bukkitToMinecraft;
        }
        Object nmsEntityType = bukkitToMinecraft.invoke(null, entityType);

        if (nmsEntityType == null) {
            return null;
        }

        Method containing = cachedBlockPosContaining;
        if (containing == null) {
            Class<?> blockPosClass = Class.forName("net.minecraft.core.BlockPos");
            containing = blockPosClass.getMethod("containing", double.class, double.class, double.class);
            cachedBlockPosContaining = containing;
        }
        Object blockPos = containing.invoke(null, location.getX(), location.getY(), location.getZ());

        Class<?> spawnReasonClass = resolveSpawnReasonClass();

        Class<?> serverLevelClass = cachedServerLevelClass;
        if (serverLevelClass == null) {
            serverLevelClass = Class.forName("net.minecraft.server.level.ServerLevel");
            cachedServerLevelClass = serverLevelClass;
        }
        @SuppressWarnings({ "rawtypes", "unchecked" })
        Object spawnReason = Enum.valueOf((Class) spawnReasonClass, "COMMAND");

        Method create = nmsEntityType.getClass().getMethod(
                "create",
                serverLevelClass,
                java.util.function.Consumer.class,
                containing.getDeclaringClass(),
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

        Class<?> nmsEntityClass = cachedNmsEntityClass;
        if (nmsEntityClass == null) {
            nmsEntityClass = Class.forName("net.minecraft.world.entity.Entity");
            cachedNmsEntityClass = nmsEntityClass;
        }

        Method addEntityToWorld = craftWorldClass.getMethod(
                "addEntityToWorld",
                nmsEntityClass,
                CreatureSpawnEvent.SpawnReason.class);

        addEntityToWorld.invoke(craftWorld, nmsEntity, CreatureSpawnEvent.SpawnReason.CUSTOM);

        Method getBukkitEntity = nmsEntity.getClass().getMethod("getBukkitEntity");
        Object bukkitEntity = getBukkitEntity.invoke(nmsEntity);

        return bukkitEntity instanceof Entity entity ? entity : null;
    }

    private static volatile Class<?> cachedSpawnReasonClass;

    private static Class<?> resolveSpawnReasonClass() throws ClassNotFoundException {
        Class<?> cached = cachedSpawnReasonClass;
        if (cached != null) return cached;

        // 1.21.2+ name
        try {
            cached = Class.forName("net.minecraft.world.entity.EntitySpawnReason");
            cachedSpawnReasonClass = cached;
            return cached;
        } catch (ClassNotFoundException ignored) {
        }

        // 1.21-1.21.1 name
        cached = Class.forName("net.minecraft.world.entity.MobSpawnType");
        cachedSpawnReasonClass = cached;
        return cached;
    }
}

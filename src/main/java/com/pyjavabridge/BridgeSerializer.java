package com.pyjavabridge;

import com.pyjavabridge.util.EnumValue;
import com.pyjavabridge.util.ObjectRegistry;

import com.google.common.collect.Multimap;
import com.google.gson.Gson;
import com.google.gson.JsonArray;
import com.google.gson.JsonElement;
import com.google.gson.JsonObject;
import net.kyori.adventure.text.Component;
import net.kyori.adventure.text.serializer.plain.PlainTextComponentSerializer;
import org.bukkit.Bukkit;
import org.bukkit.Location;
import org.bukkit.Material;
import org.bukkit.NamespacedKey;
import org.bukkit.Registry;
import org.bukkit.attribute.Attribute;
import org.bukkit.attribute.AttributeModifier;
import org.bukkit.block.Block;
import org.bukkit.block.BlockState;
import org.bukkit.block.data.BlockData;
import org.bukkit.entity.Entity;
import org.bukkit.entity.Player;
import org.bukkit.entity.Projectile;
import org.bukkit.entity.Tameable;
import org.bukkit.entity.AnimalTamer;
import org.bukkit.inventory.InventoryHolder;
import org.bukkit.inventory.ItemStack;
import org.bukkit.inventory.meta.ItemMeta;
import org.bukkit.projectiles.BlockProjectileSource;
import org.bukkit.projectiles.ProjectileSource;
import org.bukkit.util.Vector;

import java.lang.reflect.Array;
import java.lang.reflect.Method;
import java.util.ArrayList;
import java.util.Collections;
import java.util.HashMap;
import java.util.List;
import java.util.Map;
import java.util.Set;
import java.util.UUID;

public class BridgeSerializer {
    private final ObjectRegistry registry;
    private final Gson gson;
    private final PyJavaBridgePlugin plugin;

    static final Object CONVERSION_FAIL = new Object();

    public BridgeSerializer(ObjectRegistry registry, Gson gson, PyJavaBridgePlugin plugin) {
        this.registry = registry;
        this.gson = gson;
        this.plugin = plugin;
    }

    public JsonElement serialize(Object value) {
        return serialize(value, Collections.newSetFromMap(new java.util.IdentityHashMap<>()));
    }

    private JsonElement serialize(Object value, Set<Object> seen) {
        if (value == null) {
            return gson.toJsonTree(null);
        }

        if (value instanceof Number || value instanceof String || value instanceof Boolean) {
            return gson.toJsonTree(value);
        }

        if (value instanceof UUID uuid) {
            JsonObject obj = new JsonObject();
            obj.addProperty("__uuid__", uuid.toString());
            return obj;
        }

        if (value instanceof java.util.Optional<?> optional) {
            return serialize(optional.orElse(null), seen);
        }

        if (value.getClass().isEnum()) {
            JsonObject obj = new JsonObject();
            obj.addProperty("__enum__", value.getClass().getName());
            obj.addProperty("name", ((Enum<?>) value).name());
            return obj;
        }

        if (value instanceof List<?> list) {
            return gson.toJsonTree(list.stream().map(item -> serialize(item, seen)).toList());
        }

        if (value instanceof Map<?, ?> map) {
            JsonObject obj = new JsonObject();

            for (Map.Entry<?, ?> entry : map.entrySet()) {
                obj.add(entry.getKey().toString(), serialize(entry.getValue(), seen));
            }

            return obj;
        }

        if (!seen.add(value)) {
            int handle = registry.register(value);
            JsonObject obj = new JsonObject();

            obj.addProperty("__handle__", handle);
            obj.addProperty("__type__", value.getClass().getSimpleName());

            JsonObject fields = new JsonObject();

            if (value instanceof org.bukkit.block.Block block) {
                fields.addProperty("x", block.getX());
                fields.addProperty("y", block.getY());
                fields.addProperty("z", block.getZ());
            }

            if (value instanceof org.bukkit.Location location) {
                fields.addProperty("x", location.getX());
                fields.addProperty("y", location.getY());
                fields.addProperty("z", location.getZ());
                fields.addProperty("yaw", location.getYaw());
                fields.addProperty("pitch", location.getPitch());
            }

            if (value instanceof org.bukkit.entity.Player player) {
                fields.addProperty("name", player.getName());
                fields.addProperty("uuid", player.getUniqueId().toString());
            }

            if (value instanceof org.bukkit.entity.Entity entity) {
                fields.addProperty("uuid", entity.getUniqueId().toString());
            }

            if (value instanceof org.bukkit.Chunk chunk) {
                fields.addProperty("x", chunk.getX());
                fields.addProperty("z", chunk.getZ());
            }

            if (fields.size() > 0) {
                obj.add("fields", fields);
            }
            return obj;
        }

        int handle = registry.register(value);
        JsonObject obj = new JsonObject();

        obj.addProperty("__handle__", handle);
        obj.addProperty("__type__", value.getClass().getSimpleName());

        JsonObject fields = new JsonObject();

        if (value instanceof org.bukkit.entity.Player player) {
            fields.addProperty("name", player.getName());
            fields.addProperty("uuid", player.getUniqueId().toString());
            fields.add("location", serialize(player.getLocation(), seen));
            fields.add("world", serialize(player.getWorld(), seen));
            fields.add("gameMode", serialize(player.getGameMode(), seen));
            fields.addProperty("health", player.getHealth());
            fields.addProperty("foodLevel", player.getFoodLevel());
            fields.add("inventory", serialize(player.getInventory(), seen));
        }

        if (value instanceof org.bukkit.entity.Entity entity) {
            fields.addProperty("uuid", entity.getUniqueId().toString());
            fields.add("type", serialize(entity.getType(), seen));
            fields.add("location", serialize(entity.getLocation(), seen));
            fields.add("world", serialize(entity.getWorld(), seen));
            fields.addProperty("is_projectile", entity instanceof Projectile);
            addAttributionFields(entity, fields, seen);
        }

        if (value instanceof org.bukkit.World world) {
            fields.addProperty("name", world.getName());
            fields.addProperty("uuid", world.getUID().toString());
            fields.add("environment", serialize(world.getEnvironment(), seen));
        }

        if (value instanceof org.bukkit.block.Block block) {
            fields.addProperty("x", block.getX());
            fields.addProperty("y", block.getY());
            fields.addProperty("z", block.getZ());
            fields.add("location", serialize(block.getLocation(), seen));
            fields.add("type", serialize(block.getType(), seen));
            fields.add("world", serialize(block.getWorld(), seen));

            BlockState state = block.getState();
            if (state instanceof InventoryHolder holder) {
                fields.add("inventory", serialize(holder.getInventory(), seen));
            }
        }

        if (value instanceof org.bukkit.Location location) {
            fields.addProperty("x", location.getX());
            fields.addProperty("y", location.getY());
            fields.addProperty("z", location.getZ());
            fields.addProperty("yaw", location.getYaw());
            fields.addProperty("pitch", location.getPitch());

            if (location.getWorld() != null) {
                fields.add("world", serialize(location.getWorld(), seen));
            }
        }
        if (value instanceof org.bukkit.Chunk chunk) {
            fields.addProperty("x", chunk.getX());
            fields.addProperty("z", chunk.getZ());
            fields.add("world", serialize(chunk.getWorld(), seen));
        }

        if (value instanceof org.bukkit.inventory.ItemStack itemStack) {
            fields.add("type", serialize(itemStack.getType(), seen));
            fields.addProperty("amount", itemStack.getAmount());
            ItemMeta meta = itemStack.getItemMeta();

            if (meta != null) {
                if (meta.hasDisplayName()) {
                    fields.addProperty("name",
                            PlainTextComponentSerializer.plainText().serialize(meta.displayName()));
                }
                if (meta.hasLore()) {
                    List<Component> lore = meta.lore();

                    if (lore != null) {
                        List<String> loreText = new ArrayList<>();

                        for (Component component : lore) {
                            loreText.add(PlainTextComponentSerializer.plainText().serialize(component));
                        }

                        fields.add("lore", gson.toJsonTree(loreText));
                    }
                }

                if (meta.hasCustomModelData()) {
                    fields.addProperty("customModelData", meta.getCustomModelData());
                }

                JsonArray attributes = serializeAttributes(meta);
                if (attributes.size() > 0) {
                    fields.add("attributes", attributes);
                }
            }
            fields.add("nbt", serialize(itemStack.serialize(), seen));
        }

        if (value instanceof org.bukkit.potion.PotionEffect effect) {
            fields.add("type", serialize(effect.getType(), seen));
            fields.addProperty("duration", effect.getDuration());
            fields.addProperty("amplifier", effect.getAmplifier());
            fields.addProperty("ambient", effect.isAmbient());
            fields.addProperty("particles", effect.hasParticles());
            fields.addProperty("icon", effect.hasIcon());
        }

        if (value instanceof org.bukkit.inventory.Inventory inventory) {
            fields.addProperty("size", inventory.getSize());
            fields.add("contents", serialize(java.util.Arrays.asList(inventory.getContents()), seen));

            if (inventory.getHolder() != null) {
                fields.add("holder", serialize(inventory.getHolder(), seen));
            }

            try {
                Method getTitle = inventory.getClass().getMethod("getTitle");
                Object titleObj = getTitle.invoke(inventory);

                if (titleObj != null) {
                    fields.addProperty("title", titleObj.toString());
                }
            } catch (Exception ignored) {
            }
        }

        if (value instanceof org.bukkit.Server server) {
            fields.addProperty("name", server.getName());
            fields.addProperty("version", server.getVersion());
        }

        obj.add("fields", fields);
        return obj;
    }

    private void addAttributionFields(org.bukkit.entity.Entity entity, JsonObject fields, Set<Object> seen) {
        Object shooter = null;
        if (entity instanceof Projectile projectile) {
            shooter = projectile.getShooter();
        } else {
            shooter = tryInvokeNoArg(entity, "getShooter");
        }
        addAttribution("shooter", shooter, fields, seen);

        Object source = tryInvokeNoArg(entity, "getSource");
        addAttribution("source", source, fields, seen);

        Object owner = null;
        if (entity instanceof Tameable tameable) {
            fields.addProperty("is_tamed", tameable.isTamed());
            owner = tameable.getOwner();
        }
        if (owner == null) {
            owner = tryInvokeNoArg(entity, "getOwner");
        }
        if (owner == null) {
            owner = tryInvokeNoArg(entity, "getOwningPlayer");
        }
        if (owner == null) {
            owner = tryInvokeNoArg(entity, "getOwningEntity");
        }
        if (owner == null) {
            owner = tryInvokeNoArg(entity, "getSummoner");
        }
        addAttribution("owner", owner, fields, seen);
    }

    private void addAttribution(String key, Object source, JsonObject fields, Set<Object> seen) {
        if (source == null) {
            return;
        }
        if (fields.has(key)) {
            return;
        }

        Object resolved = source;
        if (source instanceof ProjectileSource projectileSource && !(source instanceof Entity)) {
            if (projectileSource instanceof BlockProjectileSource blockSource) {
                resolved = blockSource.getBlock();
            }
        }

        if ("source".equals(key) || "shooter".equals(key)) {
            if (resolved instanceof Entity sourceEntity) {
                fields.add(key, serialize(sourceEntity, seen));
            } else if (resolved instanceof org.bukkit.block.Block block) {
                fields.add(key, serialize(block, seen));
            }
            return;
        }

        if (resolved instanceof Entity sourceEntity) {
            fields.add(key, serialize(sourceEntity, seen));
            fields.addProperty(key + "_uuid", sourceEntity.getUniqueId().toString());
            if (sourceEntity instanceof Player player) {
                fields.addProperty(key + "_name", player.getName());
            } else {
                Object name = tryInvokeNoArg(sourceEntity, "getName");
                if (name instanceof String nameText && !nameText.isBlank()) {
                    fields.addProperty(key + "_name", nameText);
                }
            }
            return;
        }

        if (resolved instanceof org.bukkit.block.Block block) {
            fields.add(key, serialize(block, seen));
            return;
        }

        if (resolved instanceof AnimalTamer tamer) {
            fields.addProperty(key + "_uuid", tamer.getUniqueId().toString());
            if (tamer.getName() != null) {
                fields.addProperty(key + "_name", tamer.getName());
            }
            if (tamer instanceof Player player) {
                fields.add(key, serialize(player, seen));
            }
            return;
        }

        if (resolved instanceof UUID uuid) {
            fields.addProperty(key + "_uuid", uuid.toString());
            return;
        }

        if (resolved instanceof String nameText) {
            fields.addProperty(key + "_name", nameText);
        }
    }

    private Object tryInvokeNoArg(Object target, String methodName) {
        try {
            Method method = target.getClass().getMethod(methodName);
            if (method.getParameterCount() != 0) {
                return null;
            }
            return method.invoke(target);
        } catch (Exception ignored) {
            return null;
        }
    }

    public Object deserialize(JsonElement element) {
        if (element == null || element.isJsonNull()) {
            return null;
        }

        if (element.isJsonPrimitive()) {
            if (element.getAsJsonPrimitive().isBoolean()) {
                return element.getAsBoolean();
            }

            if (element.getAsJsonPrimitive().isNumber()) {
                return element.getAsNumber();
            }
            return element.getAsString();
        }

        if (element.isJsonArray()) {
            List<Object> list = new ArrayList<>();
            for (JsonElement child : element.getAsJsonArray()) {
                list.add(deserialize(child));
            }
            return list;
        }

        JsonObject obj = element.getAsJsonObject();

        if (obj.has("__handle__")) {
            int handle = obj.get("__handle__").getAsInt();
            return registry.get(handle);
        }

        if (obj.has("__ref__")) {
            JsonObject ref = obj.getAsJsonObject("__ref__");
            String refType = ref.has("type") ? ref.get("type").getAsString() : null;
            String refId = ref.has("id") ? ref.get("id").getAsString() : null;
            return resolveRef(refType, refId);
        }

        if (obj.has("__value__")) {
            return deserializeValueObject(obj);
        }

        if (obj.has("__uuid__")) {
            return UUID.fromString(obj.get("__uuid__").getAsString());
        }

        if (obj.has("__enum__")) {
            return new EnumValue(obj.get("__enum__").getAsString(), obj.get("name").getAsString());
        }
        return obj;
    }

    public Object resolveRef(String refType, String refId) {
        if (refType == null || refId == null) {
            return null;
        }

        return switch (refType.toLowerCase()) {
            case "player" -> {
                try {
                    yield Bukkit.getPlayer(UUID.fromString(refId));
                } catch (IllegalArgumentException ex) {
                    yield null;
                }
            }

            case "player_name" -> Bukkit.getPlayer(refId);

            case "player_inventory" -> {
                org.bukkit.entity.Player player = null;
                try {
                    player = Bukkit.getPlayer(UUID.fromString(refId));
                } catch (IllegalArgumentException ignored) {
                }
                if (player == null) {
                    player = Bukkit.getPlayer(refId);
                }
                yield player != null ? player.getInventory() : null;
            }

            case "entity" -> {
                try {
                    yield Bukkit.getEntity(UUID.fromString(refId));
                } catch (IllegalArgumentException ex) {
                    yield null;
                }
            }

            case "world" -> Bukkit.getWorld(refId);
            case "block" -> resolveBlockRef(refId);
            case "chunk" -> resolveChunkRef(refId);

            default -> null;
        };
    }

    private Object resolveBlockRef(String refId) {
        String[] parts = refId.split(":");
        if (parts.length < 4) {
            return null;
        }

        String worldName = parts[0];
        org.bukkit.World world = Bukkit.getWorld(worldName);

        if (world == null) {
            return null;
        }

        try {
            int x = Integer.parseInt(parts[1]);
            int y = Integer.parseInt(parts[2]);
            int z = Integer.parseInt(parts[3]);
            return world.getBlockAt(x, y, z);

        } catch (NumberFormatException ex) {
            return null;
        }
    }

    private Object resolveChunkRef(String refId) {
        String[] parts = refId.split(":");

        if (parts.length < 3) {
            return null;
        }

        String worldName = parts[0];
        org.bukkit.World world = Bukkit.getWorld(worldName);

        if (world == null) {
            return null;
        }

        try {
            int x = Integer.parseInt(parts[1]);
            int z = Integer.parseInt(parts[2]);
            return world.getChunkAt(x, z);

        } catch (NumberFormatException ex) {
            return null;
        }
    }

    private Object deserializeValueObject(JsonObject obj) {
        String valueType = obj.get("__value__").getAsString();
        JsonObject fields = obj.has("fields") ? obj.getAsJsonObject("fields") : new JsonObject();

        return switch (valueType) {

            case "Location" -> {
                double x = fields.has("x") ? fields.get("x").getAsDouble() : 0.0;
                double y = fields.has("y") ? fields.get("y").getAsDouble() : 0.0;
                double z = fields.has("z") ? fields.get("z").getAsDouble() : 0.0;

                float yaw = fields.has("yaw") ? fields.get("yaw").getAsFloat() : 0f;
                float pitch = fields.has("pitch") ? fields.get("pitch").getAsFloat() : 0f;

                org.bukkit.World world = null;

                if (fields.has("world")) {
                    Object worldObj = deserialize(fields.get("world"));

                    if (worldObj instanceof org.bukkit.World w) {
                        world = w;

                    } else if (worldObj instanceof String name) {
                        world = Bukkit.getWorld(name);
                    }
                }

                yield new Location(world, x, y, z, yaw, pitch);
            }

            case "Vector" -> {
                double x = fields.has("x") ? fields.get("x").getAsDouble() : 0.0;
                double y = fields.has("y") ? fields.get("y").getAsDouble() : 0.0;
                double z = fields.has("z") ? fields.get("z").getAsDouble() : 0.0;

                yield new Vector(x, y, z);
            }

            case "Item", "ItemStack" -> {
                Object typeObj = fields.has("type") ? deserialize(fields.get("type")) : null;
                Material material = null;

                if (typeObj instanceof EnumValue enumValue) {
                    material = Material.matchMaterial(enumValue.name);

                } else if (typeObj instanceof String text) {
                    material = Material.matchMaterial(text);
                }

                if (material == null) {
                    material = Material.AIR;
                }

                ItemStack stack = null;

                if (fields.has("nbt")) {
                    stack = deserializeItemFromNbt(fields.get("nbt"));
                }

                if (stack == null) {
                    int amount = fields.has("amount") ? fields.get("amount").getAsInt() : 1;
                    stack = new ItemStack(material, amount);
                }

                if (stack != null) {
                    ItemMeta meta = stack.getItemMeta();

                    if (meta != null) {
                        if (fields.has("name")) {
                            meta.displayName(Component.text(fields.get("name").getAsString()));
                        }

                        if (fields.has("lore") && fields.get("lore").isJsonArray()) {
                            List<Component> lore = new ArrayList<>();

                            for (JsonElement element : fields.getAsJsonArray("lore")) {
                                if (!element.isJsonNull()) {
                                    lore.add(Component.text(element.getAsString()));
                                }
                            }
                            meta.lore(lore);
                        }

                        if (fields.has("customModelData")) {
                            meta.setCustomModelData(fields.get("customModelData").getAsInt());
                        }

                        if (fields.has("attributes")) {
                            applyAttributes(meta, fields.get("attributes"));
                        }

                        stack.setItemMeta(meta);
                    }
                }

                yield stack;
            }

            case "ItemMeta" -> {
                Object typeObj = fields.has("type") ? deserialize(fields.get("type")) : null;
                Material material = null;

                if (typeObj instanceof EnumValue enumValue) {
                    material = Material.matchMaterial(enumValue.name);

                } else if (typeObj instanceof String text) {
                    material = Material.matchMaterial(text);
                }

                if (material == null) {
                    material = Material.STONE;
                }
                org.bukkit.inventory.meta.ItemMeta meta = Bukkit.getItemFactory().getItemMeta(material);

                if (meta == null) {
                    yield null;
                }

                if (fields.has("customModelData")) {
                    meta.setCustomModelData(fields.get("customModelData").getAsInt());
                }

                if (fields.has("lore") && fields.get("lore").isJsonArray()) {
                    List<Component> lore = new ArrayList<>();

                    for (JsonElement element : fields.getAsJsonArray("lore")) {
                        Object loreObj = deserialize(element);
                        if (loreObj != null) {
                            lore.add(Component.text(loreObj.toString()));
                        }
                    }
                    meta.lore(lore);
                }
                yield meta;
            }

            case "Effect" -> {
                Object typeObj = fields.has("type") ? deserialize(fields.get("type")) : null;
                org.bukkit.potion.PotionEffectType effectType = null;

                String keyName = null;

                if (typeObj instanceof EnumValue enumValue) {
                    keyName = enumValue.name;

                } else if (typeObj instanceof String text) {
                    keyName = text;
                }

                if (keyName != null) {
                    if (keyName.contains(":")) {
                        org.bukkit.NamespacedKey key = org.bukkit.NamespacedKey.fromString(keyName.toLowerCase());

                        if (key != null) {
                            effectType = org.bukkit.Registry.POTION_EFFECT_TYPE.get(key);
                        }

                    } else {
                        effectType = org.bukkit.Registry.POTION_EFFECT_TYPE
                                .get(org.bukkit.NamespacedKey.minecraft(keyName.toLowerCase()));
                    }
                }

                if (effectType == null) {
                    yield null;
                }

                int duration = fields.has("duration") ? fields.get("duration").getAsInt() : 0;
                int amplifier = fields.has("amplifier") ? fields.get("amplifier").getAsInt() : 0;

                boolean ambient = fields.has("ambient") && fields.get("ambient").getAsBoolean();
                boolean particles = !fields.has("particles") || fields.get("particles").getAsBoolean();
                boolean icon = !fields.has("icon") || fields.get("icon").getAsBoolean();

                yield new org.bukkit.potion.PotionEffect(effectType, duration, amplifier, ambient, particles, icon);
            }
            case "Inventory" -> {
                int size = fields.has("size") ? fields.get("size").getAsInt() : 9;
                String title = fields.has("title") ? fields.get("title").getAsString() : "";

                org.bukkit.inventory.Inventory inventory = Bukkit.createInventory(null, size,
                        Component.text(title));

                if (fields.has("contents") && fields.get("contents").isJsonArray()) {
                    int index = 0;

                    for (JsonElement element : fields.getAsJsonArray("contents")) {
                        Object itemObj = deserialize(element);

                        if (itemObj instanceof ItemStack itemStack) {
                            inventory.setItem(index, itemStack);
                        }

                        index++;
                        if (index >= size) {
                            break;
                        }
                    }
                }
                yield inventory;
            }
            case "Block" -> {
                org.bukkit.World world = null;
                if (fields.has("world")) {
                    Object worldObj = deserialize(fields.get("world"));

                    if (worldObj instanceof org.bukkit.World w) {
                        world = w;

                    } else if (worldObj instanceof String name) {
                        world = Bukkit.getWorld(name);
                    }
                }

                if (world == null) {
                    yield null;
                }

                int x = fields.has("x") ? fields.get("x").getAsInt() : 0;
                int y = fields.has("y") ? fields.get("y").getAsInt() : 0;
                int z = fields.has("z") ? fields.get("z").getAsInt() : 0;

                Block block = world.getBlockAt(x, y, z);

                if (fields.has("type")) {
                    Object typeObj = deserialize(fields.get("type"));
                    Material material = null;

                    if (typeObj instanceof EnumValue enumValue) {
                        material = Material.matchMaterial(enumValue.name);

                    } else if (typeObj instanceof String text) {
                        material = Material.matchMaterial(text);

                    }
                    if (material != null) {
                        block.setType(material);
                    }
                }
                yield block;
            }

            case "World" -> {
                String name = fields.has("name") ? fields.get("name").getAsString() : null;
                yield name != null ? Bukkit.getWorld(name) : null;
            }

            case "Entity" -> {
                String uuid = fields.has("uuid") ? fields.get("uuid").getAsString() : null;
                yield uuid != null ? resolveRef("entity", uuid) : null;
            }

            case "Player" -> {
                String uuid = fields.has("uuid") ? fields.get("uuid").getAsString() : null;
                yield uuid != null ? resolveRef("player", uuid) : null;
            }
            default -> obj;
        };
    }

    public Object[] convertArgs(Class<?>[] parameterTypes, List<Object> args) {
        Object[] converted = new Object[parameterTypes.length];

        for (int i = 0; i < parameterTypes.length; i++) {
            Object arg = args.get(i);

            Class<?> parameterType = parameterTypes[i];

            if (parameterType.isArray()) {
                Object arrayValue = convertArrayArg(parameterType, arg);

                if (arrayValue == CONVERSION_FAIL) {
                    return null;
                }

                converted[i] = arrayValue;
                continue;
            }

            Object value = convertArg(parameterType, arg);

            if (value == CONVERSION_FAIL) {
                return null;
            }
            converted[i] = value;
        }

        return converted;
    }

    private Object convertArrayArg(Class<?> parameterType, Object arg) {
        if (arg == null) {
            return null;
        }

        if (parameterType.isInstance(arg)) {
            return arg;
        }
        Class<?> componentType = parameterType.getComponentType();

        if (arg instanceof List<?> list) {
            Object array = Array.newInstance(componentType, list.size());

            for (int index = 0; index < list.size(); index++) {
                Object element = list.get(index);
                Object convertedElement = convertArg(componentType, element);

                if (convertedElement == CONVERSION_FAIL) {
                    return CONVERSION_FAIL;
                }
                Array.set(array, index, convertedElement);
            }
            return array;
        }
        Object convertedElement = convertArg(componentType, arg);

        if (convertedElement == CONVERSION_FAIL) {
            return CONVERSION_FAIL;
        }

        Object array = Array.newInstance(componentType, 1);
        Array.set(array, 0, convertedElement);
        return array;

    }

    public Object convertArg(Class<?> parameterType, Object arg) {
        if (arg == null) {
            return null;
        }

        if (arg instanceof Boolean) {
            if (parameterType == boolean.class || parameterType == Boolean.class) {
                return arg;
            }
            return CONVERSION_FAIL;
        }

        if (parameterType.isInstance(arg)) {
            return arg;
        }

        if (parameterType == int.class || parameterType == Integer.class) {
            return arg instanceof Number number ? number.intValue() : CONVERSION_FAIL;
        }

        if (parameterType == double.class || parameterType == Double.class) {
            return arg instanceof Number number ? number.doubleValue() : CONVERSION_FAIL;
        }

        if (parameterType == float.class || parameterType == Float.class) {
            return arg instanceof Number number ? number.floatValue() : CONVERSION_FAIL;
        }

        if (parameterType == long.class || parameterType == Long.class) {
            return arg instanceof Number number ? number.longValue() : CONVERSION_FAIL;
        }

        if (parameterType == boolean.class || parameterType == Boolean.class) {
            return arg;
        }

        if (parameterType.isEnum() && arg instanceof EnumValue enumValue) {
            @SuppressWarnings("unchecked")
            Class<? extends Enum<?>> enumClass = (Class<? extends Enum<?>>) parameterType;

            @SuppressWarnings({ "rawtypes", "unchecked" })

            Enum<?> enumValueResolved = Enum.valueOf((Class) enumClass, enumValue.name);
            return enumValueResolved;
        }

        if (parameterType == UUID.class && arg instanceof UUID uuid) {
            return uuid;
        }

        if (Component.class.isAssignableFrom(parameterType) && arg instanceof String str) {
            return Component.text(str);
        }

        if (parameterType.isEnum() && arg instanceof String str) {
            try {
                @SuppressWarnings({ "rawtypes", "unchecked" })
                Enum<?> enumVal = Enum.valueOf((Class) parameterType, str.toUpperCase());
                return enumVal;
            } catch (IllegalArgumentException e) {
                return CONVERSION_FAIL;
            }
        }

        if (BlockData.class.isAssignableFrom(parameterType)) {
            String matName = null;
            if (arg instanceof String str) {
                matName = str;
            } else if (arg instanceof EnumValue enumValue) {
                matName = enumValue.name;
            }
            if (matName != null) {
                try {
                    return Bukkit.createBlockData(Material.valueOf(matName.toUpperCase()));
                } catch (IllegalArgumentException e) {
                    return CONVERSION_FAIL;
                }
            }
        }

        return CONVERSION_FAIL;
    }

    public Map<String, Object> deserializeArgsObject(JsonObject argsObj) {
        Map<String, Object> options = new HashMap<>();

        if (argsObj != null) {
            for (Map.Entry<String, JsonElement> entry : argsObj.entrySet()) {
                options.put(entry.getKey(), deserialize(entry.getValue()));
            }
        }

        return options;
    }

    public Object getField(Object target, String field) throws Exception {
        String getterName = "get" + capitalize(field);
        try {
            Method getter = target.getClass().getMethod(getterName);
            return getter.invoke(target);
        } catch (NoSuchMethodException ignored) {
        }
        String isName = "is" + capitalize(field);
        try {
            Method getter = target.getClass().getMethod(isName);
            return getter.invoke(target);
        } catch (NoSuchMethodException ignored) {
        }
        return target.getClass().getField(field).get(target);
    }

    public void setField(Object target, String field, Object value) throws Exception {
        String setterName = "set" + capitalize(field);
        for (Method method : target.getClass().getMethods()) {
            if (!method.getName().equals(setterName) || method.getParameterCount() != 1) {
                continue;
            }
            Object[] converted = convertArgs(method.getParameterTypes(), List.of(value));
            if (converted != null) {
                method.invoke(target, converted);
                return;
            }
        }
        target.getClass().getField(field).set(target, value);
    }

    JsonArray serializeAttributes(ItemMeta meta) {
        JsonArray array = new JsonArray();
        Multimap<Attribute, AttributeModifier> modifiers = meta.getAttributeModifiers();

        if (modifiers == null) {
            return array;
        }

        for (Map.Entry<Attribute, AttributeModifier> entry : modifiers.entries()) {
            Attribute attribute = entry.getKey();
            AttributeModifier modifier = entry.getValue();
            JsonObject obj = new JsonObject();

            if (attribute.getKey() != null) {
                obj.addProperty("attribute", attribute.getKey().toString());
            }

            if (modifier.getKey() != null) {
                obj.addProperty("key", modifier.getKey().toString());
            }

            obj.addProperty("amount", modifier.getAmount());
            obj.addProperty("operation", modifier.getOperation().name());
            array.add(obj);
        }
        return array;
    }

    void applyAttributes(ItemMeta meta, JsonElement attributesElement) {
        if (attributesElement == null || !attributesElement.isJsonArray()) {
            return;
        }
        meta.setAttributeModifiers(null);
        for (JsonElement element : attributesElement.getAsJsonArray()) {
            if (!element.isJsonObject()) {
                continue;
            }

            JsonObject obj = element.getAsJsonObject();
            String attributeKey = obj.has("attribute") ? obj.get("attribute").getAsString() : null;

            if (attributeKey == null) {
                continue;
            }

            NamespacedKey namespacedKey = NamespacedKey.fromString(attributeKey);
            if (namespacedKey == null) {
                continue;
            }

            Attribute attribute = Registry.ATTRIBUTE.get(namespacedKey);
            if (attribute == null) {
                continue;
            }

            NamespacedKey modifierKey = null;
            if (obj.has("key")) {
                modifierKey = NamespacedKey.fromString(obj.get("key").getAsString());
            }

            if (modifierKey == null) {
                modifierKey = new NamespacedKey(plugin, "attr_" + UUID.randomUUID());
            }

            double amount = obj.has("amount") ? obj.get("amount").getAsDouble() : 0.0;

            AttributeModifier.Operation operation = AttributeModifier.Operation.ADD_NUMBER;

            if (obj.has("operation")) {
                try {
                    operation = AttributeModifier.Operation.valueOf(obj.get("operation").getAsString());
                } catch (IllegalArgumentException ignored) {
                }
            }

            AttributeModifier modifier = new AttributeModifier(modifierKey, amount, operation);
            meta.addAttributeModifier(attribute, modifier);
        }
    }

    List<Map<String, Object>> attributeList(ItemMeta meta) {
        List<Map<String, Object>> list = new ArrayList<>();
        Multimap<Attribute, AttributeModifier> modifiers = meta.getAttributeModifiers();
        if (modifiers == null) {
            return list;
        }
        for (Map.Entry<Attribute, AttributeModifier> entry : modifiers.entries()) {
            Attribute attribute = entry.getKey();
            AttributeModifier modifier = entry.getValue();
            Map<String, Object> entryMap = new HashMap<>();
            if (attribute.getKey() != null) {
                entryMap.put("attribute", attribute.getKey().toString());
            }
            if (modifier.getKey() != null) {
                entryMap.put("key", modifier.getKey().toString());
            }
            entryMap.put("amount", modifier.getAmount());
            entryMap.put("operation", modifier.getOperation().name());
            list.add(entryMap);
        }
        return list;
    }

    ItemStack deserializeItemFromNbt(JsonElement nbtElement) {
        if (nbtElement == null || nbtElement.isJsonNull()) {
            return null;
        }
        if (!nbtElement.isJsonObject()) {
            return null;
        }
        @SuppressWarnings("unchecked")
        Map<String, Object> map = gson.fromJson(nbtElement, Map.class);
        try {
            return ItemStack.deserialize(map);
        } catch (Exception ex) {
            return null;
        }
    }

    private static String capitalize(String value) {
        if (value == null || value.isEmpty()) {
            return value;
        }
        return value.substring(0, 1).toUpperCase() + value.substring(1);
    }
}

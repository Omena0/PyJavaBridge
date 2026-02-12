package com.pyjavabridge.facade;

import com.pyjavabridge.PyJavaBridgePlugin;

import java.lang.reflect.Method;
import java.util.ArrayList;
import java.util.List;
import java.util.Map;
import java.util.UUID;

import org.bukkit.Bukkit;
import org.bukkit.permissions.PermissionAttachment;

public class PermissionsFacade {
    private final PyJavaBridgePlugin plugin;
    private final Map<UUID, PermissionAttachment> permissionAttachments;

    public PermissionsFacade(PyJavaBridgePlugin plugin, Map<UUID, PermissionAttachment> permissionAttachments) {
        this.plugin = plugin;
        this.permissionAttachments = permissionAttachments;
    }

    public boolean addPermission(org.bukkit.entity.Player player, String permission, boolean value) {
        if (player == null || permission == null) { return false; }
        if (applyLuckPermsPermission(player, permission, value)) { return true; }
        PermissionAttachment attachment = permissionAttachments.computeIfAbsent(player.getUniqueId(),
                id -> player.addAttachment(plugin));
        attachment.setPermission(permission, value);
        return true;
    }

    public boolean removePermission(org.bukkit.entity.Player player, String permission) {
        if (player == null || permission == null) { return false; }
        if (applyLuckPermsRemovePermission(player, permission)) { return true; }
        PermissionAttachment attachment = permissionAttachments.get(player.getUniqueId());
        if (attachment == null) { return false; }
        attachment.unsetPermission(permission);
        return true;
    }

    public List<String> groups(org.bukkit.entity.Player player) {
        if (player == null) { return List.of(); }
        List<String> result = luckPermsGroups(player);
        return result != null ? result : List.of();
    }

    public String primaryGroup(org.bukkit.entity.Player player) {
        if (player == null) { return null; }
        return luckPermsPrimaryGroup(player);
    }

    public boolean hasGroup(org.bukkit.entity.Player player, String group) {
        if (player == null || group == null) { return false; }
        List<String> groups = luckPermsGroups(player);
        if (groups == null) { return false; }
        return groups.contains(group);
    }

    public boolean addGroup(org.bukkit.entity.Player player, String group) {
        if (player == null || group == null) { return false; }
        return applyLuckPermsGroup(player, group, true);
    }

    public boolean removeGroup(org.bukkit.entity.Player player, String group) {
        if (player == null || group == null) { return false; }
        return applyLuckPermsGroup(player, group, false);
    }

    private Object luckPermsApi() {
        try {
            Class<?> apiClass = Class.forName("net.luckperms.api.LuckPerms");
            Object registration = Bukkit.getServicesManager().getRegistration(apiClass);
            if (registration == null) { return null; }
            Method getProvider = registration.getClass().getMethod("getProvider");
            return getProvider.invoke(registration);
        } catch (Exception e) {
            return null;
        }
    }

    private Object luckPermsUser(Object api, UUID uuid) {
        try {
            Object userManager = api.getClass().getMethod("getUserManager").invoke(api);
            Method getUser = userManager.getClass().getMethod("getUser", UUID.class);
            return getUser.invoke(userManager, uuid);
        } catch (Exception e) {
            return null;
        }
    }

    private boolean saveLuckPermsUser(Object api, Object user) {
        try {
            Object userManager = api.getClass().getMethod("getUserManager").invoke(api);
            Class<?> userClass = Class.forName("net.luckperms.api.model.user.User");
            Method saveUser = userManager.getClass().getMethod("saveUser", userClass);
            saveUser.invoke(userManager, user);
            return true;
        } catch (Exception e) {
            return false;
        }
    }

    private boolean applyLuckPermsPermission(org.bukkit.entity.Player player, String permission, boolean value) {
        Object api = luckPermsApi();
        if (api == null) { return false; }
        Object user = luckPermsUser(api, player.getUniqueId());
        if (user == null) { return false; }
        try {
            Class<?> nodeClass = Class.forName("net.luckperms.api.node.Node");
            Object builder = nodeClass.getMethod("builder", String.class).invoke(null, permission);
            builder.getClass().getMethod("value", boolean.class).invoke(builder, value);
            Object node = builder.getClass().getMethod("build").invoke(builder);
            Object data = user.getClass().getMethod("data").invoke(user);
            data.getClass().getMethod("add", nodeClass).invoke(data, node);
            return saveLuckPermsUser(api, user);
        } catch (Exception e) {
            return false;
        }
    }

    private boolean applyLuckPermsRemovePermission(org.bukkit.entity.Player player, String permission) {
        Object api = luckPermsApi();
        if (api == null) { return false; }
        Object user = luckPermsUser(api, player.getUniqueId());
        if (user == null) { return false; }
        try {
            Class<?> nodeClass = Class.forName("net.luckperms.api.node.Node");
            Object builder = nodeClass.getMethod("builder", String.class).invoke(null, permission);
            Object node = builder.getClass().getMethod("build").invoke(builder);
            Object data = user.getClass().getMethod("data").invoke(user);
            data.getClass().getMethod("remove", nodeClass).invoke(data, node);
            return saveLuckPermsUser(api, user);
        } catch (Exception e) {
            return false;
        }
    }

    private boolean applyLuckPermsGroup(org.bukkit.entity.Player player, String group, boolean add) {
        Object api = luckPermsApi();
        if (api == null) { return false; }
        Object user = luckPermsUser(api, player.getUniqueId());
        if (user == null) { return false; }
        try {
            Class<?> nodeClass = Class.forName("net.luckperms.api.node.types.InheritanceNode");
            Object builder = nodeClass.getMethod("builder", String.class).invoke(null, group);
            Object node = builder.getClass().getMethod("build").invoke(builder);
            Object data = user.getClass().getMethod("data").invoke(user);
            if (add) {
                data.getClass().getMethod("add", nodeClass).invoke(data, node);
            } else {
                data.getClass().getMethod("remove", nodeClass).invoke(data, node);
            }
            return saveLuckPermsUser(api, user);
        } catch (Exception e) {
            return false;
        }
    }

    private List<String> luckPermsGroups(org.bukkit.entity.Player player) {
        Object api = luckPermsApi();
        if (api == null) { return null; }
        Object user = luckPermsUser(api, player.getUniqueId());
        if (user == null) { return null; }
        try {
            Class<?> inheritanceNodeClass = Class.forName("net.luckperms.api.node.types.InheritanceNode");
            Object nodes = user.getClass().getMethod("getNodes").invoke(user);
            if (!(nodes instanceof Iterable<?> iterable)) { return List.of(); }
            List<String> groups = new ArrayList<>();
            for (Object node : iterable) {
                if (inheritanceNodeClass.isInstance(node)) {
                    Object name = inheritanceNodeClass.getMethod("getGroupName").invoke(node);
                    if (name != null) { groups.add(name.toString()); }
                }
            }
            return groups;
        } catch (Exception e) {
            return List.of();
        }
    }

    private String luckPermsPrimaryGroup(org.bukkit.entity.Player player) {
        Object api = luckPermsApi();
        if (api == null) { return null; }
        Object user = luckPermsUser(api, player.getUniqueId());
        if (user == null) { return null; }
        try {
            Object group = user.getClass().getMethod("getPrimaryGroup").invoke(user);
            return group != null ? group.toString() : null;
        } catch (Exception e) {
            return null;
        }
    }
}

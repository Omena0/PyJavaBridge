package com.pyjavabridge.facade;

public class ReflectFacade {
    public Class<?> clazz(String name) throws ClassNotFoundException {
        return Class.forName(name);
    }
}

package com.pyjavabridge.client;

public final class ClientModProtocol {
    private ClientModProtocol() {
    }

    public static final String CHANNEL = "pyjavabridge:client_mod";
    public static final int MAGIC = 0x504A;
    public static final int PROTOCOL_VERSION = 1;

    public static final int HELLO = 0x01;
    public static final int HELLO_ACK = 0x02;
    public static final int COMMAND_REQUEST = 0x03;
    public static final int COMMAND_RESPONSE = 0x04;
    public static final int PERMISSION_REQUEST = 0x05;
    public static final int PERMISSION_DECISION = 0x06;
    public static final int SCRIPT_REGISTER = 0x07;
    public static final int SCRIPT_RESULT = 0x08;
    public static final int CUSTOM_DATA = 0x09;
    public static final int ERROR = 0x0A;
    public static final int HEARTBEAT = 0x0B;

    public static final int MAX_BODY_BYTES = 16_777_216;
}

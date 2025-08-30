package tak.server.plugins;

import atakmap.commoncommo.protobuf.v1.MessageOuterClass.Message;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;

import java.io.BufferedReader;
import java.io.File;
import java.io.InputStreamReader;
import java.io.OutputStreamWriter;
import java.nio.charset.StandardCharsets;
import java.util.concurrent.atomic.AtomicLong;

@TakServerPlugin(
    name = "Meshtastic Interceptor",
    description = "Intercepts CoT messages with __meshtastic detail and sends them over mesh network")
public class MeshtasticInterceptorPlugin extends MessageInterceptorBase {

    private static final Logger logger = LoggerFactory.getLogger(MeshtasticInterceptorPlugin.class);
    private static final String MESHTASTIC_DETAIL_KEY = "__meshtastic";
    private static final String PYTHON_SCRIPT = "meshtastic_sender.py";
    
    private AtomicLong messageCount = new AtomicLong(0);
    private AtomicLong meshtasticMessageCount = new AtomicLong(0);
    private String pythonScriptPath;
    private boolean enabled = true;
    private String meshtasticInterface = "serial";
    private String meshtasticPort = "/dev/ttyUSB0";

    public MeshtasticInterceptorPlugin() {
        // Load configuration in constructor
        if (config != null) {
            if (config.containsProperty("enabled")) {
                enabled = (Boolean) config.getProperty("enabled");
            }
            if (config.containsProperty("interface")) {
                meshtasticInterface = (String) config.getProperty("interface");
            }
            if (config.containsProperty("port")) {
                meshtasticPort = (String) config.getProperty("port");
            }
        }
    }

    @Override
    public void start() {
        logger.info("Meshtastic Interceptor Plugin starting");
        
        // Setup Python script path
        File pluginDir = new File("/opt/tak/conf/plugins");
        pythonScriptPath = new File(pluginDir, PYTHON_SCRIPT).getAbsolutePath();
        
        logger.info("Meshtastic plugin initialized - Interface: {}, Port: {}, Enabled: {}", 
                   meshtasticInterface, meshtasticPort, enabled);
    }

    @Override
    public void stop() {
        logger.info("Meshtastic Interceptor Plugin stopping. Total messages: {}, Meshtastic messages: {}", 
                   messageCount.get(), meshtasticMessageCount.get());
    }

    @Override
    public Message intercept(Message message) {
        if (!enabled) {
            return message;
        }
        
        messageCount.incrementAndGet();
        
        try {
            Message.Builder mb = message.toBuilder();
            
            // Check if message has Payload with CotEvent
            if (mb.hasPayload() && mb.getPayloadBuilder().hasCotEvent()) {
                // Get the XML detail
                String xmlDetail = mb.getPayloadBuilder().getCotEventBuilder().getDetailBuilder().getXmlDetail();
                
                // Check for __meshtastic in detail
                if (xmlDetail != null && xmlDetail.contains(MESHTASTIC_DETAIL_KEY)) {
                    meshtasticMessageCount.incrementAndGet();
                    
                    // Extract CoT XML from the message
                    String cotXml = extractCotXml(mb);
                    
                    // Send via Meshtastic
                    sendToMeshtastic(cotXml);
                    
                    logger.debug("Intercepted and sent Meshtastic message #{}", meshtasticMessageCount.get());
                }
            }
        } catch (Exception e) {
            logger.error("Error processing message in Meshtastic interceptor", e);
        }
        
        // Return the original message unchanged
        return message;
    }
    
    private String extractCotXml(Message.Builder mb) {
        // Convert Message back to simplified CoT XML format
        // This is a simplified version - you may need to enhance based on actual requirements
        StringBuilder cotXml = new StringBuilder();
        cotXml.append("<event");
        
        var cotEventBuilder = mb.getPayloadBuilder().getCotEventBuilder();
        
        String uid = cotEventBuilder.getUid();
        if (uid != null && !uid.isEmpty()) {
            cotXml.append(" uid=\"").append(uid).append("\"");
        }
        
        String type = cotEventBuilder.getType();
        if (type != null && !type.isEmpty()) {
            cotXml.append(" type=\"").append(type).append("\"");
        }
        
        String how = cotEventBuilder.getHow();
        if (how != null && !how.isEmpty()) {
            cotXml.append(" how=\"").append(how).append("\"");
        }
        
        long sendTime = cotEventBuilder.getSendTime();
        if (sendTime > 0) {
            cotXml.append(" time=\"").append(sendTime).append("\"");
        }
        
        long startTime = cotEventBuilder.getStartTime();
        if (startTime > 0) {
            cotXml.append(" start=\"").append(startTime).append("\"");
        }
        
        long staleTime = cotEventBuilder.getStaleTime();
        if (staleTime > 0) {
            cotXml.append(" stale=\"").append(staleTime).append("\"");
        }
        cotXml.append(">");
        
        // Add point if present
        double lat = cotEventBuilder.getLat();
        double lon = cotEventBuilder.getLon();
        if (lat != 0.0 || lon != 0.0) {
            cotXml.append("<point lat=\"").append(lat)
                  .append("\" lon=\"").append(lon);
            
            double hae = cotEventBuilder.getHae();
            if (hae != 0.0) {
                cotXml.append("\" hae=\"").append(hae);
            }
            
            double ce = cotEventBuilder.getCe();
            if (ce != 0.0) {
                cotXml.append("\" ce=\"").append(ce);
            }
            
            double le = cotEventBuilder.getLe();
            if (le != 0.0) {
                cotXml.append("\" le=\"").append(le);
            }
            cotXml.append("\"/>");
        }
        
        // Add detail
        String xmlDetail = cotEventBuilder.getDetailBuilder().getXmlDetail();
        if (xmlDetail != null && !xmlDetail.isEmpty()) {
            cotXml.append("<detail>");
            cotXml.append(xmlDetail);
            cotXml.append("</detail>");
        }
        
        cotXml.append("</event>");
        
        return cotXml.toString();
    }
    
    private void sendToMeshtastic(String cotXml) {
        try {
            // Call Python script to send via Meshtastic
            ProcessBuilder pb = new ProcessBuilder(
                "python3", pythonScriptPath,
                "--interface", meshtasticInterface,
                "--port", meshtasticPort
            );
            pb.redirectErrorStream(true);
            
            Process process = pb.start();
            
            // Send CoT XML to Python script via stdin
            try (OutputStreamWriter writer = new OutputStreamWriter(
                    process.getOutputStream(), StandardCharsets.UTF_8)) {
                writer.write(cotXml);
                writer.flush();
            }
            
            // Read response
            try (BufferedReader reader = new BufferedReader(
                    new InputStreamReader(process.getInputStream()))) {
                String line;
                while ((line = reader.readLine()) != null) {
                    logger.debug("Meshtastic script output: {}", line);
                }
            }
            
            int exitCode = process.waitFor();
            if (exitCode != 0) {
                logger.warn("Meshtastic script exited with code: {}", exitCode);
            }
            
        } catch (Exception e) {
            logger.error("Failed to send message via Meshtastic", e);
        }
    }
}
# TAK Server Plugin SDK
## Requirements
Java 17

This branch (master) currently contains the SDK and sample builds for TAK and 4.10 (See TAK_Server_Configuration_Guide.pdf for installation instructions).

This branch (master) always corresponds to the latest release of TAK Server. You can check out maintenance branches for older versions of the SDK. For example https://git.tak.gov/sdks/takserver/tak-server-sdk/-/tree/maintenance/4.8

Installers available here:

https://artifacts.tak.gov/ui/repos/tree/General/TAKServer

## Dev Environment
Linux or macOS is recommended for development. If using Windows, replace "gradlew" with "gradlew.bat" in commands below.

Your artifacts.tak.gov credentials will need to be stored in ~/.gradle/gradle.properties as takGovUser and takGovPassword for access to the plugin support library.

Eclipse IDE

## Overview of TAK Server Plugins
### Plugin Architecture: Goals

- Extension of the core TAK server platform without core code changes
- Simple interfaces for use by plugin developers. 
- Ease of plugin configuration, including UI
- Decoupling of plugin code from messaging and API code (execution of plugins in a separate process)

The plugin capability is designed to provide as much flexibility as possible to plugin developers, while maintaining a concise and simple framework for integration with TAK Server.

### Plugin Types
| Type | Base Class | Function |
| :--- | :--- | :--- |
| Message Sender | MessageSenderBase | Sends messages from the plugin to TAK Server (and clients, federates and other plugins), using the TAK proto messaging format.|
| Message Receiver | MessageReceiverBase | Receives messages from TAK Server (client messages, federated messages, and messages from MessageSender plugins), using the TAK proto messaging format. |
| Message Sender and Receiver | MessageSenderReceiverBase | Sends messages to and receives messages from TAK Server (and clients, federates and other plugins), using the TAK proto messaging format. |
| Message Interceptor | MessageInterceptorBase | Intercept messages after they are received by TAK Server from clients or federates, but before the messages are broadcast out to receiving clients. Plugin code can modify or enrich each message that is intercepted. |


#### Plugin Annotations and Metadata
Plugin classes must be annotated at the class level with the `@TakServerPlugin` annotation. The plugin name defaults to simple class name. The name can be overriden, and a description (optional) can also be included.

```
@TakServerPlugin(
		name = "Periodic Sender Example",
		description = "Example plugin that sends data on a time interval")
public class PeriodicMessageSenderPlugin extends MessageSenderBase {
```

Plugin classes can optionally be annotated at the class level with the `@TakServerPluginVersion` annotation. This annotation allows for the definition of major, minor, patch, commitHash and tag. By default, these values will be set to the current git information of the SDK repository when a build is generated.

```
@TakServerPluginVersion(
		major = 4,
		minor = 6,
		patch = 1,
		commitHash = "hash",
		tag = "tag")
```

#### Plugin Internal APIs
When developing a plugin, you will have access to `systemInfoApi` object. This object is a protected member of the Plugins base class. 

Current available methods via the `systemInfoApi`:
- `getTAKServerUrl()` : Returns: the value defined in the TAK Server CoreConfig.xml => Federation => Federation-Server => webBaseUrl property

# Message Format
TAK Server plugins use the TAK proto message format to send and receive messages. This data format applies the fast and efficient data encoding of Protocol Buffers to Cursor on Target (CoT). Information about the format and definitions:

https://git.tak.gov/standards/takproto

## Plugin Development
### Overview
To develop a plugin, extend one of the base classes listed above (such as MessageInterceptorBase). The projects in the SDK are intended as examples of how to structure a plugin project. Interfaces and utility functions that are used and extended by TAK Server plugins are contained in the plugins jar located in the `src/lib` folder in the SDK repo. Plugin projects must be compiled against this jar, as shown in the examples.

The simplest way to develop a plugin is to copy one of the example subprojects, and start modifying the copied project to implement your plugin. Several sample plugins are included to demonstrate how plugins work:

| Project Name | Class Name | Purpose |
| :------------------------------- | :------------------------------- | :------------------------------- | 
| takserver-receiver-plugin-sample | MessageLoggingReceiverPlugin | Receive messages from TAK Server and log them to the plugin log file. |
| takserver-sender-plugin-sample | PeriodicMessageSenderPlugin | Send messages to TAK Server. These messages can be received by TAK clients, federates and MessageReceiver plugins - subject to message addressing and group filtering. Includes examples of addressing to individual clients, and groups. |
| takserver-sender-plugin-sample-http | PeriodicHttpConvertingMessageSenderPlugin | Make periodic HTTP calls to a URL, and render the reponses as the content of TAK Proto messages. |
| takserver-sender-receiver-message-forwarder-plugin-sample | MessageForwarderPlugin | Received messages from TAK Server, make a simple modification to the messages and re-send them to TAK Server. | 
| takserver-sender-receiver-periodic-logging-plugin-sample | PeriodicSenderAndLoggingReceiverPlugin | Periodically send messages to TAK Server and logs the messages it receives. |
| takserver-interceptor-message-counter-sample | MessageInterceptorCounterPlugin | This plugin will intercept messages, and mark them with an atomic counter of messages intercepted. |
| takserver-interceptor-random-uid-injector-sample | MessageInterceptorUuidInjectorPlugin  | This plugin will intercept messages, and inject a random UUID in the XML detail field of each intercepted message. |
| takserver-submit-data-plugin-sample | SubmitDataPlugin  | Send, read, update and delete data to a plugin through an API call. See below for more details. |
| takserver-sender-plugin-datafeed | DataFeedMessageSenderPlugin | Create, query, and delete datafeed. Periodically send messages to a datafeed. Demonstrate how to programmatically self-stop the plugin after a period of time. |
| takserver-sender-plugin-mission | MissionMessageSenderPlugin | Create, query, update and delete missions. | 
| takserver-file-plugin-sample | FilePlugin | Performs CRUD and search on files. |
| takserver-file-plugin-sample | FileUploadListenerPlugin | Example plugin that listens to file upload event. |


_Note on interceptor plugins: This is a new plugin type added in TAK Server version 4.5. Interceptor plugins are linked together in a chain pattern when executed. This design allows one or more plugins to operate on an individual message. Since message interception occurs in the core streaming message processing pipeline for clients, ensure that interceptor plugins are as fast and efficien t as possible to avoid introducing delays in message processing._

In Eclipse, choose `File -> Import -> Gradle -> Existing Gradle Project` to import a plugin project into your workspace.

### Recommended Development Workflow
The TAK Server Plugin SDK contains examples plugins, and a recommended gradle build that builds the examples.

To develop your own plugin, you can copy the contents of the SDK, copy one of the sample plugins to a new directory, and manage the code in your own git repo. Don't try to push any commits to the TAK Server Plugin SDK repo.

Example workflow:

1. Plugin developer clones SDK repo
2. In <localdir>/takserver-sdk/src, copy one of the sample plugins as a starting point, i.e. takserver-myplugin
3. Delete other example plugin dirs from <localdir>/takserver-sdk/src if desired.
4. Push your modifed copy of <localdir>/takserver-sdk/src, including your new plugin code to your own git repo.
5. Make commits and iterate on takserver-myplugin.

### Required Java Package
TAK Server plugins must compiled in a Java package that is a subpackage of 'tak.server.plugins', like 'tak.server.plugins.mypluginpackage'. If your plugin is not contained in this package, it will not be loaded.

### Dependencies
When developing a plugin, you may need to use an open-source, 3rd-party or other Java library. For example, the `takserver-sender-plugin-sample-http` uses the Apache HTTP client to make HTTP requests. 

The `takserver-sender-plugin-sample-http` uses a gradle plugin called Shadow to repack dependencies directly into the plugin JAR file. Due to this repacking, only a single JAR is needed to load the plugin and all of its dependencies - this simplifies plugin management. See https://github.com/johnrengelman/shadow for more info about generating shadow jars.

Alternatively (if a shadow jar is not used), dependencies can be placed in `/opt/tak/lib/deps`. JARs placed here will be loaded by the TAK Server plugin manager and can be used by plugins. 

### Message Groups and Addresses
If no groups are specified in the Message object, plugin messages will be sent to the special `__ANON__` group. By populating the the `groups` `destClientUids` and `destCallsigns` lists in the Message object, messages can be directed to groups or indiviudals. Individual clients can be addressed by their client UID (recommended) or callsign (not recommended, as it is a user-specified value.)

### Plugin Configuration
Plugin options can be set in a customized in a YAML configuration file that is specific to each plugin. Plugin configuration files are located in `/opt/tak/conf/plugins`. *If it doesn't already exist, an empty configuration file will be generated for each plugin the first time it is run.* The name of the plugin configuration file is the fully-qualified name of the plugin, appended with the extension `.yaml`. For example, the configuration file for the  sample PeriodicHttpConvertingMessageSenderPlugin is located at `/opt/tak/conf/plugins/tak.server.plugins.PeriodicHttpConvertingMessageSenderPlugin.yaml`.

Other than two reserved keys: `tak` and `system`, the YAML configuration for each plugin is entirely open-ended. `tak` and `system` can't be used for plugin configuration - they are reserved for future use. When writing a plugin, take advantage of the YAML config file to specify any options that are needed for your plugin.

The plugin superclass (MessageSenderBase or MessageReceiverBase) provides a `config` object for accessing the contents of the YAML config. Use this object to access config options. For example, to access

```
long interval;

if (config.containsProperty("interval")) {
  interval = Long.valueOf((int)config.getProperty("interval"));
}
```

If the config file can't be parse due to invalid structure, illegal YAML or use of reserved configuration keys, the plugin will fail startup and an error will be shown in the plugin admin UI.

See `takserver-sender-plugin-sample-http` for an example of using a YAML option for a HTTP URL and a time interval.

### Conversion of CoT Events
A utility method is provided to convert a CoT string into its equivalent TAK Protobuf Java object representation, as shown here. Use the `getConverter()` utility method to obtain the message converter instance:

```
// CoT String
String cot = "<event version=\"2.0\" uid=\"ANDROID-352413144215585\" type=\"a-f-G-U-C\" how=\"m-g\" time=\"2020-02-12T13:16:07Z\" start=\"2020-02-12T13:16:05Z\" stale=\"2020-02-12T13:16:50Z\"><point lat=\"40.255716\" lon=\"-72.045306\" hae=\"-22.22983896651138\" ce=\"4.9\" le=\"9999999.0\"/><detail><__group name=\"Dark Blue\" role=\"Team Member\"/><precisionlocation geopointsrc=\"GPS\" altsrc=\"GPS\"/><status battery=\"32\"/><takv device=\"SAMSUNG SM-G975U1\" platform=\"ATAK-CIV\" os=\"29\" version=\"3.12.0-45691.45691-CIV\"/><track speed=\"0.0\" course=\"344.72362164876733\"/><contact endpoint=\"*:-1:stcp\" phone=\"19999999999\" callsign=\"coolata\"/><uid Droid=\"coolata\"/></detail></event>";

// convert the CoT string into a TAK Protobuf Message
Message message = getConverter().cotStringToDataMessage(SA, groups);, Integer.toString(System.identityHashCode(this)));
```

### Logging
The plugin log file is located here: `/opt/tak/logs/takserver-plugins.log`. Plugins can log to this file, using sl4j and logback. See the sample plugins for examples. Use caution when logging, as frequent logging can consume a lot of disk space. In particular, writing a log message for 

### Build and run sample plugins

Save your artifacts.tak.gov credentials to `~/.gradle/gradle.properties` to be used by the plugin as follows:  
```
takGovUser=tak.user@email.com
takGovPassword=p@ssw0rd
```

Build it as follows:  
```
cd <repo-home>/src
./gradlew clean shadowJar
```

If you have a stale maven dependency for the plugins jar, use this command to download fresh maven dependencies while building:
```
cd <repo-home>/src
./gradlew clean shadowJar --refresh-dependencies
```

Copy sample plugins to a TAK Server. On an standalone place plugin JAR files here: `/opt/tak/lib`. You can also use the docker configuration by creating a `lib` folder within the `tak` directory contained in the takserver-docker archive and placing your plugin there.  

Once built, compiled jars for the sample plugins are located in the build/libs directory for each plugin. For example:
```
takserver-sender-plugin-sample/build/libs
takserver-receiver-plugin-sample/build/libs
```

Restart TAK Server to reload plugins.

```
sudo systemctl restart takserver
```

View plugin manager UI to see plugins loaded. This requires a client cert configured for admin access (see TAK Server configuration guide for information.)
```
https://<tak_server_hostname>:8443/Marti/plugins/
```


connect a local nc client to see messages generated by sample sender plugin (unsecure input on port 8088 must be enabled - not for production use)
```
nc localhost 8088
```

### Submit data API 

The API takes all request parameters and passes them to the plugin in a map for flexibility. Current supported verbs are PUT, POST, GET, and DELETE.

The API path is `/Marti/api/plugins/<plugin-name>/submit` followed by any request parameters

The plugin name can be any plugin which is imported into takserver and which implement the methods within SumbitDataPlugin

PUT will call onSubmitData or onSubmitDataWithResult depending on the path. The two different options are the following 
- `/Marti/api/plugins/<plugin-name>/submit`
- `/Marti/api/plugins/<plugin-name>/submit/result`

If result is included in the path, a successful PUT will also return the data sent in the request. 

Example curl command for sample plugin:
```
curl -k -v -X PUT "https://localhost:8443/Marti/api/plugins/tak.server.plugins.SubmitDataPlugin/submit?scope=fademist" -H "accept: */*" -H "Content-Type: application/xml" -H "Pragma: no-cache" -H "Cache-Control: no-cache" -d "<event version='2.0' uid='anon1' type='a-f-G-U-C' time='2015-03-09T18:06:56.935Z' start='2015-03-09T18:06:56.935Z' stale='2015-03-09T18:07:23.935Z' how='h-g-i-g-o'><point lat='20.0' lon='-10.0' hae='9999999.0' ce='9999999' le='9999999' /><detail><contact endpoint='127.0.0.1:4242:tcp' phone='' callsign='anon1'/><__group role='Team Member' name='Green'/><status battery='9'/><track course='289.81913691958033' speed='0.0'/><precisionlocation geopointsrc='???' altsrc='???'/><takv platform='atak' version='999'/></detail></event>" --cert <path-to-cert>.p12:atakatak --cert-type P12
```

POST will call onUpdateData in the plugin. For the example plugin, the method will only return success if the POST request updates an already existing value in the map. 

Example curl command for sample plugin:
```
curl -k -v -X POST "https://localhost:8443/Marti/api/plugins/tak.server.plugins.SubmitDataPlugin/submit?scope=fademist" -H "accept: */*" -H "Content-Type: application/xml" -H "Pragma: no-cache" -H "Cache-Control: no-cache" -d "<event version='2.0' uid='anon1' type='a-f-G-U-C' time='2015-03-09T18:06:56.935Z' start='2015-03-09T18:06:56.935Z' stale='2015-03-09T18:07:23.935Z' how='h-g-i-g-o'><point lat='20.0' lon='-10.0' hae='9999999.0' ce='9999999' le='9999999' /><detail><contact endpoint='127.0.0.1:4242:tcp' phone='' callsign='anon1'/><__group role='Team Member' name='Blue'/><status battery='9'/><track course='289.81913691958033' speed='0.0'/><precisionlocation geopointsrc='?' altsrc='?'/><takv platform='atak' version='999'/></detail></event>" --cert <path-to-cert>:atakatak --cert-type P12
```

GET will call onRequestData in the plugin. For the example plugin, it returns the previous value stored for the provided scope if it exists. 

Example curl command for sample plugin:
```
curl -k -v -X GET "https://localhost:8443/Marti/api/plugins/tak.server.plugins.SubmitDataPlugin/submit?scope=fademist" -H "accept: application/json" -H "Content-Type: application/xml" -H "Pragma: no-cache" -H "Cache-Control: no-cache" --cert <path-to-cert>:atakatak --cert-type P12
```

DELETE will call onDeleteData in the plugin with the requested parameters. In the example plugin, it deletes the value stored with the provided scope. 

Example curl command for sample plugin:
```
curl -k -v -X DELETE "https://localhost:8443/Marti/api/plugins/tak.server.plugins.SubmitDataPlugin/submit?scope=fademist" -H "accept: application/json" -H "Content-Type: application/xml" -H "Pragma: no-cache" -H "Cache-Control: no-cache" --cert <path-to-cert>:atakatak --cert-type P12
```


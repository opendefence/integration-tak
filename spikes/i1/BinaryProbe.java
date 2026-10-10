import java.nio.file.Files;
import java.nio.file.Path;
import java.security.cert.CertificateFactory;
import java.security.cert.X509Certificate;
import java.util.Arrays;
import java.util.List;
import java.util.Set;

import com.bbn.marti.config.Input;
import com.bbn.marti.groups.DistributedPersistentGroupManager;
import com.bbn.marti.groups.FileAuthenticator;
import com.bbn.marti.groups.InMemoryGroupStore;
import com.bbn.marti.groups.X509Authenticator;
import com.bbn.marti.remote.RemoteContact;
import com.bbn.marti.remote.config.CoreConfigFacade;
import com.bbn.marti.remote.config.DistributedConfiguration;
import com.bbn.marti.remote.config.LocalConfiguration;
import com.bbn.marti.remote.groups.AuthStatus;
import com.bbn.marti.remote.groups.AuthenticatedUser;
import com.bbn.marti.remote.groups.ConnectionType;
import com.bbn.marti.remote.groups.Direction;
import com.bbn.marti.remote.util.SpringContextBeanForApi;
import com.bbn.marti.remote.util.RemoteUtil;
import com.bbn.marti.service.DistributedContactManager;
import com.bbn.marti.service.SubmissionService;
import com.bbn.marti.service.SubscriptionStore;
import com.bbn.marti.util.MessagingDependencyInjectionProxy;
import com.bbn.marti.xml.bindings.Role;
import org.apache.ignite.configuration.IgniteConfiguration;
import org.apache.ignite.spi.discovery.tcp.TcpDiscoverySpi;
import org.apache.ignite.spi.discovery.tcp.ipfinder.vm.TcpDiscoveryVmIpFinder;
import org.dom4j.DocumentHelper;
import org.springframework.context.support.GenericApplicationContext;
import tak.server.cot.CotEventContainer;
import tak.server.ignite.IgniteConfigurationHolder;
import tak.server.ignite.IgniteHolder;

/** Executes selected, unmodified TAK classes. This is not a live TAK server test. */
public class BinaryProbe {
    private static final String UUID = "00000000-0000-4000-8000-000000000001";

    private static X509Certificate certificate(String name) throws Exception {
        try (var input = Files.newInputStream(Path.of(name + ".pem"))) {
            return (X509Certificate) CertificateFactory.getInstance("X.509").generateCertificate(input);
        }
    }

    private static void check(boolean condition, String message) {
        if (!condition) throw new AssertionError(message);
    }

    public static void main(String[] args) throws Exception {
        System.setProperty("spring.profiles.active", "config");
        LocalConfiguration.doUpgrades = false;
        var config = CoreConfigFacade.getInstance().getRemoteConfiguration();
        config.getRepository().setEnable(false);
        config.getAuth().setX509AddAnonymous(false);
        config.getAuth().setX509Groups(false);
        config.getAuth().setX509UseGroupCache(false);
        config.getAuth().setX509CheckRevocation(false);
        config.getAuth().setX509TokenAuth(false);
        var igniteConfig = new IgniteConfiguration();
        igniteConfig.setLocalHost("127.0.0.1");
        igniteConfig.setDiscoverySpi(new TcpDiscoverySpi().setIpFinder(
            new TcpDiscoveryVmIpFinder().setAddresses(List.of("127.0.0.1:47500"))));
        IgniteConfigurationHolder.getInstance().setIgniteConfiguration(igniteConfig);
        try (var ignite = IgniteHolder.getInstance().getIgnite();
             var spring = new GenericApplicationContext()) {
            var groupManager = new DistributedPersistentGroupManager();
            var store = new InMemoryGroupStore();
            var contacts = new SubscriptionStore();
            var injection = new MessagingDependencyInjectionProxy();
            spring.getBeanFactory().registerSingleton("groupManager", groupManager);
            spring.getBeanFactory().registerSingleton("groupStore", store);
            spring.getBeanFactory().registerSingleton("subscriptionStore", contacts);
            spring.getBeanFactory().registerSingleton("simpleCoreConfig", DistributedConfiguration.getInstance());
            spring.getBeanFactory().registerSingleton("injection", injection);
            spring.refresh();
            injection.setApplicationContext(spring);
            new SpringContextBeanForApi().setApplicationContext(spring);
            var fileAuth = FileAuthenticator.getInstance();
            fileAuth.initFile();
            var registration = fileAuth.getAllUsers().iterator().next();
            check(fileAuth.getAllUsers().size() == 1, "exactly one UUID account required");
            check(registration.getIdentifier().equals(UUID), "wrong fixture identifier");
            check(registration.getRole() == Role.ROLE_READONLY, "wrong fixture role");
            // Disabled LDAP, cache, token, revocation and admin paths do not use these services.
            var auth = new X509Authenticator(groupManager, null, null, null);
            var input = new Input();
            input.setAuthRequired(true);
            input.setAnongroup(false);
            var ca = certificate("ca");
            var names = List.of("main", "tak-only", "unapproved", "other-uuid");
            var leaves = new java.util.HashSet<String>();
            for (var name : names) {
                var cert = certificate(name);
                cert.checkValidity();
                cert.verify(ca.getPublicKey());
                check(leaves.add(RemoteUtil.getInstance().getCertSHA256Fingerprint(cert)), "duplicate fixture leaf");
            }
            for (var registered : List.of("main", "tak-only")) {
                var registeredFingerprint = RemoteUtil.getInstance().getCertSHA256Fingerprint(certificate(registered));
                registration.setFingerprint(registeredFingerprint);
                check(fileAuth.getAllUsers().iterator().next().getFingerprint().equals(registeredFingerprint),
                    "stored fingerprint did not update");
                for (var name : names) {
                    var cert = certificate(name);
                    var cn = name.equals("other-uuid") ? "00000000-0000-4000-8000-000000000002" : UUID;
                    var user = new AuthenticatedUser(cn, registered + "-" + name, "127.0.0.1", cert,
                        cn, "", "", ConnectionType.CORE);
                    var status = auth.authenticate(user, input);
                    var granted = user.getAuthorities().contains("ROLE_READONLY");
                    var anonymous = user.getAuthorities().contains("ROLE_ANONYMOUS");
                    var groups = groupManager.getGroups(user);
                    var groupNames = groups.stream().map(group -> group.getName()).collect(java.util.stream.Collectors.toSet());
                    var directions = groups.stream().map(group -> group.getDirection()).collect(java.util.stream.Collectors.toSet());
                    System.out.printf(
                        "RESULT stored=%s presented=%s status=%s role_readonly=%s role_anonymous=%s group_names=%s group_entries=%d%n",
                        registered, name, status, granted, anonymous, groupNames, groups.size());
                    check(status == AuthStatus.SUCCESS, "unexpected authentication status");
                    check(granted == !name.equals("other-uuid"), "binary behavior changed; investigate");
                    check(anonymous == name.equals("other-uuid"), "unexpected anonymous authority");
                    check(groups.size() == 2, "unexpected group count: " + groups.size());
                    check(groupNames.equals(Set.of(granted ? "fixture" : "__ANON__")),
                        "unexpected group names: " + groupNames);
                    check(directions.equals(Set.of(Direction.IN, Direction.OUT)), "unexpected group directions: " + directions);
                }
            }
            var before = certificate("main").getEncoded();
            var manager = new DistributedContactManager();
            manager.addContact(new RemoteContact().setUid("fixture-cot-uid").setContactName("CLIENT"));
            var renamed = new RemoteContact(contacts.getContactByContactUid("fixture-cot-uid"));
            renamed.setContactName("DESIRED");
            manager.updateContact(renamed);
            check(manager.getCallsignFromUid("fixture-cot-uid").equals("DESIRED"), "contact update failed");
            check(contacts.getViewOfConnectionSubMap().isEmpty(), "contact update created a subscription");
            System.out.println("RESULT contact_update=DESIRED subscriptions=0");
            // Invoke only the contact handler; no server lifecycle or message routing runs here.
            var submission = new SubmissionService(null, null, null, null, groupManager, null, null,
                null, null, null, ignite, null, contacts, null, manager, null, null, null,
                RemoteUtil.getInstance(), null, null, null);
            var processContact = SubmissionService.class.getDeclaredMethod("processContactMessage", CotEventContainer.class);
            processContact.setAccessible(true);
            var cot = new CotEventContainer(DocumentHelper.parseText("""
                <event version="2.0" uid="fixture-cot-uid" type="a-f-G-U-C" how="m-g"
                    time="2026-10-10T00:00:00Z" start="2026-10-10T00:00:00Z" stale="2026-10-10T00:01:00Z">
                  <point lat="0" lon="0" hae="0" ce="9999999" le="9999999"/>
                  <detail><contact callsign="CLIENT-NEXT" endpoint="127.0.0.1:4242:tcp"/></detail>
                </event>
                """));
            processContact.invoke(submission, cot);
            check(manager.getCallsignFromUid("fixture-cot-uid").equals("CLIENT-NEXT"), "CoT did not replace contact name");
            check(contacts.getContactByContactUid("fixture-cot-uid").getEndpoint().equals("127.0.0.1:4242:tcp"),
                "CoT endpoint did not reach the contact store");
            check(contacts.getViewOfConnectionSubMap().isEmpty(), "contact handler created a subscription");
            check(Arrays.equals(before, certificate("main").getEncoded()), "leaf changed");
            check(fileAuth.getAllUsers().size() == 1 && registration.getIdentifier().equals(UUID), "account changed");
            check(registration.getRole() == Role.ROLE_READONLY && registration.getGroupList().equals(List.of("fixture")),
                "permissions changed");
            System.out.println("RESULT next_cot_contact=CLIENT-NEXT desired_overwritten=true leaf_unchanged=true account_unchanged=true permissions_unchanged=true subscriptions=0");
            System.out.println("RESULT approved_set_requirement=FAIL unapproved_same_uuid_received_role_and_groups");
            // The disposable container must not wait for TAK's process-wide executor shutdown hooks.
            Runtime.getRuntime().halt(0);
        }
    }
}

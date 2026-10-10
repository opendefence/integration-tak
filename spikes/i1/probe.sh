#!/bin/sh
set -eu
cd /work
mkdir war
cd war
jar xf /artifacts/takserver.war
cd /work
classpath='/work/war/WEB-INF/classes:/work/war/WEB-INF/lib/*'
cat > CoreConfig.xml <<'XML'
<Configuration xmlns="http://bbn.com/marti/xml/config">
  <network version="5.8-RELEASE-84"/>
  <auth default="file" x509addAnonymous="false"><File location="UserAuthenticationFile.xml"/></auth>
</Configuration>
XML
cat > TAKIgniteConfig.xml <<'XML'
<TAKIgniteConfiguration xmlns="http://bbn.com/marti/xml/config"/>
XML
cat > UserAuthenticationFile.xml <<'XML'
<UserAuthenticationFile xmlns="http://bbn.com/marti/xml/bindings">
  <User identifier="00000000-0000-4000-8000-000000000001" role="ROLE_READONLY"><groupList>fixture</groupList></User>
</UserAuthenticationFile>
XML
openssl req -x509 -newkey rsa:2048 -nodes -days 1 -subj /CN=I1-fixture-CA -keyout ca.key -out ca.pem 2>/dev/null
for name in main tak-only unapproved other-uuid; do
  cn=00000000-0000-4000-8000-000000000001
  if [ "$name" = other-uuid ]; then cn=00000000-0000-4000-8000-000000000002; fi
  openssl req -new -newkey rsa:2048 -nodes -subj "/CN=$cn" -keyout "$name.key" -out "$name.csr" 2>/dev/null
  openssl x509 -req -in "$name.csr" -CA ca.pem -CAkey ca.key -CAcreateserial -days 1 -out "$name.pem" 2>/dev/null
  openssl verify -CAfile ca.pem "$name.pem"
done
javac -cp "$classpath" -d /work /probe/BinaryProbe.java
timeout 30s java -XX:ActiveProcessorCount=2 --add-opens=java.base/java.nio=ALL-UNNAMED \
  --add-opens=java.base/sun.nio.ch=ALL-UNNAMED --add-opens=java.base/java.lang=ALL-UNNAMED \
  --add-opens=java.base/java.util=ALL-UNNAMED --add-opens=java.base/java.io=ALL-UNNAMED \
  -cp "/work:$classpath" BinaryProbe

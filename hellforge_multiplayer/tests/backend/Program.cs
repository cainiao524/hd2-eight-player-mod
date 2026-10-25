// Exercises the actual pinned GPL HellForge services with synthetic identities.
// The transport is a deterministic queue: no sockets, Steam, pipes or game process.
using System.Text.Json;
using HellForge.LocalBackend.Multiplayer;

var checks = 0;
void Check(bool ok, string message) {
    if (!ok) throw new InvalidDataException(message);
    checks++;
}
var bus = new Bus();
var nodes = Enumerable.Range(1, 9).Select(i => new Node(bus, (ulong)i, "research-v1")).ToArray();
var host = nodes[0];
var empty = new Dictionary<string, string>();
Frame Create(int capacity) => new Frame("lobby.create").Add("create").Add(host.Entity).Add("title_player_account")
    .Add(capacity).Add(0).Add(0).Add(0).Add(empty).Add(empty).Add(empty);
Frame Join(Node n, string connection) => new Frame("lobby.join").Add("join").Add(n.Entity).Add("title_player_account").Add(connection).Add(empty);
host.Lobby.FromLocal(Create(8)); bus.Drain();
var created = host.Take("lobby.result");
Check(created.Text(2) == "0" && created.Int(6) == 8, "eight-member lobby creation");
var lobby = created.Text(3); var connection = created.Text(4);
host.Party.FromLocal(new Frame("party.host").Add("synthetic-network").Add(8).Add(8).Add(1).Add(1).Add(1).Add(0));

void Connect(Node n, bool allowed) {
    n.Party.FromLocal(new Frame("party.connect").Add("connect").Add("synthetic-network").Add(host.Entity)); bus.Drain();
    var reply = n.Take("party.connected");
    Check((reply.Int(1) == 0) == allowed, "Party membership authorization");
    if (allowed) {
        Check(reply.Int(3) == 8 && reply.Int(4) == 8, "Party configuration round trip");
        n.Endpoint = (ushort)reply.Int(9);
    }
}
Connect(nodes[8], false);
var mismatch = new Node(bus, 100, "other-mods");
mismatch.Lobby.FromLocal(Join(mismatch, connection)); bus.Drain();
Check(mismatch.Take("lobby.result").Text(2) == LobbyService.ModlistMismatch.ToString(System.Globalization.CultureInfo.InvariantCulture), "mod mismatch refused before capacity filled");
for (int i = 1; i < 8; ++i) {
    var n = nodes[i]; n.Lobby.FromLocal(Join(n, connection)); bus.Drain();
    var joined = n.Take("lobby.result"); Check(joined.Int(2) == 0, $"member {i + 1} joins");
    int at = 10; joined.Properties(ref at); joined.Properties(ref at);
    Check(joined.Int(at) == i + 1, "complete member snapshot");
    Connect(n, true);
}
host.Endpoint = 1;
foreach (var n in nodes.Take(8)) {
    n.Party.FromLocal(new Frame("party.endpoint").Add("synthetic-network").Add("endpoint").Add(n.Endpoint).Add(n.Entity)); bus.Drain();
    Check(n.Take("party.endpointCreated", f => f.Text(1) == "endpoint").Int(2) == n.Endpoint, "unique endpoint ownership");
}
Check(nodes.Take(8).Select(n => n.Endpoint).Distinct().Count() == 8, "eight unique endpoint IDs");
Check(host.Party.Peers().Count == 7, "host sees seven remote nodes");
nodes[8].Lobby.FromLocal(Join(nodes[8], connection)); bus.Drain();
Check(nodes[8].Take("lobby.result").Text(2) == LobbyService.LobbyNotJoinable.ToString(System.Globalization.CultureInfo.InvariantCulture), "ninth lobby member refused");
Connect(nodes[8], false);

// Every one of the eight endpoints sends to all seven others through the real router.
// Optional integration payloads come from the native x64 property producer.
// They are a format bridge, not complete serialized game datagrams.
if (args.Length != 0) {
    Check(args.Length == 4 && args[0] == "--native-roster-input" && args[2] == "--native-roster-output", "native fixture arguments");
    var input = File.ReadAllBytes(args[1]);
    using var fixture = JsonDocument.Parse(input);
    var packets = fixture.RootElement.GetProperty("packets").EnumerateArray().ToArray();
    Check(fixture.RootElement.GetProperty("schema").GetString() == "native_roster_property_fixture_v1" && packets.Length == 8,
        "native property fixture schema");
    Check(packets.Select(p => p.GetProperty("sender").GetInt32()).Order().SequenceEqual(Enumerable.Range(1, 8)), "one payload per sender");
    var deliveries = new List<object>();
    var firstCheck = checks;
    foreach (var packet in packets) {
        var sender = nodes[packet.GetProperty("sender").GetInt32() - 1];
        var payload = Convert.FromBase64String(packet.GetProperty("payload").GetString()!);
        Check(payload.Length == 32, "eight property words");
        foreach (var n in nodes) n.Frames.Clear();
        sender.Party.FromLocal(new Frame("party.message").Add("synthetic-network").Add(sender.Endpoint)
            .Add(PartyService.GuaranteedDelivery).Add("").Add(payload)); bus.Drain();
        foreach (var recipient in nodes.Take(8).Where(n => n != sender)) {
            var message = recipient.Take("party.message");
            Check(message.Int(1) == sender.Endpoint && message.Bytes(4).SequenceEqual(payload), "native property routing integrity");
            Check(recipient.Frames.All(f => f.Type != "party.message"), "one delivery per recipient");
            deliveries.Add(new { sender = (int)sender.Id, recipient = (int)recipient.Id,
                endpoint = message.Int(1), payload = Convert.ToBase64String(message.Bytes(4)) });
        }
        Check(sender.Frames.All(f => f.Type != "party.message") && nodes[8].Frames.Count == 0, "native data no echo or outsider");
    }
    Check(deliveries.Count == 56, "all 56 native property deliveries");
    File.WriteAllText(args[3], JsonSerializer.Serialize(new {
        input_sha256 = Convert.ToHexString(System.Security.Cryptography.SHA256.HashData(input)).ToLowerInvariant(),
        relay_checks = checks - firstCheck, deliveries, game_access = false, steam_transport_tested = false
    }, new JsonSerializerOptions { WriteIndented = true }));
}
foreach (var sender in nodes.Take(8)) {
    foreach (var n in nodes) n.Frames.Clear();
    byte[] payload = [0, (byte)sender.Id, 255, 0, 128];
    sender.Party.FromLocal(new Frame("party.message").Add("synthetic-network").Add(sender.Endpoint)
        .Add(PartyService.GuaranteedDelivery).Add("").Add(payload)); bus.Drain();
    foreach (var recipient in nodes.Take(8).Where(n => n != sender)) {
        var message = recipient.Take("party.message");
        Check(message.Int(1) == sender.Endpoint && message.Bytes(4).SequenceEqual(payload), "all-to-all payload integrity");
    }
    Check(sender.Frames.All(f => f.Type != "party.message") && nodes[8].Frames.Count == 0, "no echo or outsider delivery");
}
foreach (var n in nodes) n.Frames.Clear();
nodes[7].Party.FromLocal(new Frame("party.message").Add("synthetic-network").Add(nodes[7].Endpoint).Add(1)
    .Add(nodes[2].Endpoint.ToString()).Add(new byte[] {42})); bus.Drain();
Check(nodes[2].Take("party.message").Bytes(4).SequenceEqual(new byte[] {42}), "targeted routing");
Check(nodes.Where(n => n != nodes[2]).All(n => n.Frames.All(f => f.Type != "party.message")), "targeted message stays scoped");

// An occupied identity reconnects at full capacity: one member, no stale endpoint.
var returning = nodes[3]; var oldEndpoint = returning.Endpoint;
returning.Lobby.FromLocal(Join(returning, connection)); bus.Drain();
Check(returning.Take("lobby.result").Int(2) == 0, "full-lobby reconnect succeeds without a ninth member");
Connect(returning, true);
Check(returning.Endpoint == oldEndpoint, "reconnect retains its assigned endpoint block");
returning.Party.FromLocal(new Frame("party.endpoint").Add("synthetic-network").Add("again").Add(returning.Endpoint).Add(returning.Entity)); bus.Drain();
Check(returning.Take("party.endpointCreated", f => f.Text(1) == "again").Int(2) == oldEndpoint, "stale endpoint removed before reuse");
host.Party.PeerLost(returning.Id); host.Lobby.PeerLost(returning.Id); bus.Drain();
Check(!host.Party.Peers().Contains(returning.Id) && !host.Lobby.InHostedLobby(returning.Id), "lost peer removed from both layers");
returning.Lobby.FromLocal(Join(returning, connection)); bus.Drain();
Check(returning.Take("lobby.result").Int(2) == 0, "member rejoins after peer loss");
Connect(returning, true);
foreach (var n in nodes) n.Frames.Clear();
host.Party.LocalDisconnected(); host.Lobby.LocalDisconnected(); bus.Drain();
foreach (var n in nodes.Skip(1).Take(7)) {
    Check(n.Frames.Count(f => f.Type == "party.networkGone") == 1, "host exit closes each remote network");
    Check(n.Frames.Any(f => f.Type == "lobby.disconnected"), "host exit closes each remote lobby");
}
Console.WriteLine(JsonSerializer.Serialize(new { suite = "hellforge_backend_eight_nodes", checks, passed = true,
    synthetic_nodes = 8, game_clients = 0, game_access = false, steam_transport_tested = false,
    multiplayer_verified = false }));

sealed class Bus {
    readonly Dictionary<ulong, Link> links = new();
    readonly Queue<(ulong From, ulong To, byte[] Bytes)> queue = new();
    public IPeerTransport Join(ulong id) => links[id] = new Link(this, id);
    public void Drain() {
        int delivered = 0;
        while (queue.TryDequeue(out var packet)) {
            if (++delivered > 10000) throw new InvalidDataException("frame loop");
            if (links.TryGetValue(packet.To, out var link)) link.Deliver(packet.From, packet.Bytes);
        }
    }
    sealed class Link(Bus bus, ulong id) : IPeerTransport {
        public ulong LocalId => id;
        public event Action<ulong, byte[]>? Received;
        public void Start() { }
        public void Send(ulong peer, byte[] frame, bool reliable) => bus.queue.Enqueue((id, peer, frame.ToArray()));
        public void Deliver(ulong peer, byte[] bytes) => Received?.Invoke(peer, bytes);
        public void Dispose() => bus.links.Remove(id);
    }
}
sealed class Node {
    public readonly ulong Id;
    public string Entity => LobbyService.EntityId(Id);
    public readonly List<Frame> Frames = new();
    public readonly LobbyService Lobby;
    public readonly PartyService Party;
    public ushort Endpoint;
    public Node(Bus bus, ulong id, string digest) {
        Id = id; var transport = bus.Join(id);
        Lobby = new LobbyService(transport, Frames.Add, _ => {}, digest);
        Party = new PartyService(transport, Frames.Add, _ => {}, Lobby.InHostedLobby);
        transport.Received += (peer, bytes) => {
            var frame = Frame.Decode(bytes);
            if (frame.Type.StartsWith("party.", StringComparison.Ordinal)) Party.FromPeer(peer, frame);
            else if (frame.Type != "war.clock") Lobby.FromPeer(peer, frame);
        };
    }
    public Frame Take(string type, Func<Frame, bool>? predicate = null) {
        int at = Frames.FindIndex(f => f.Type == type && (predicate?.Invoke(f) ?? true));
        if (at < 0) throw new InvalidDataException($"Node {Id} missing {type}");
        var frame = Frames[at]; Frames.RemoveAt(at); return frame;
    }
}

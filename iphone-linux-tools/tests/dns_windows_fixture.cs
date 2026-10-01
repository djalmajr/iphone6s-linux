namespace IphoneDns
{
    using System;
    using System.Collections.Generic;
    using System.Diagnostics;
    using System.IO;
    using System.Net;
    using System.Net.Sockets;
    using System.Text;
    using System.Threading;

    public sealed class DnsAssertionException : Exception
    {
        public DnsAssertionException(string message) : base(message) { }
    }

    internal sealed class RecordSpec
    {
        internal byte[] Owner = new byte[] { 192, 12 };
        internal int Type = 1;
        internal int Group = 1;
        internal uint Ttl = 30;
        internal byte[] Data = new byte[] { 172, 16, 42, 1 };
    }

    internal static class Packets
    {
        internal static byte[] Name(string value)
        {
            List<byte> data = new List<byte>();
            foreach (string label in value.Split('.'))
            {
                data.Add((byte)label.Length);
                data.AddRange(Encoding.ASCII.GetBytes(label));
            }
            data.Add(0);
            return data.ToArray();
        }

        internal static void U16(List<byte> output, int value)
        {
            output.Add((byte)(value >> 8)); output.Add((byte)value);
        }

        internal static void Record(List<byte> output, RecordSpec record)
        {
            output.AddRange(record.Owner);
            U16(output, record.Type); U16(output, record.Group);
            output.Add((byte)(record.Ttl >> 24)); output.Add((byte)(record.Ttl >> 16));
            output.Add((byte)(record.Ttl >> 8)); output.Add((byte)record.Ttl);
            U16(output, record.Data.Length);
            output.AddRange(record.Data);
        }

        internal static byte[] Reply(byte[] question, string mode)
        {
            List<byte> result = new List<byte>(question);
            result[2] = 0x84; result[3] = 0; result[7] = 1;
            RecordSpec answer = new RecordSpec();
            if (mode == "literal" || mode == "question-name") answer.Owner = Name("iphone-usb.home.arpa");
            if (mode == "owner") answer.Owner = Name("other.home.arpa");
            if (mode == "address") answer.Data = new byte[] { 172, 16, 42, 9 };
            if (mode == "record-class") answer.Group = 3;
            if (mode == "answer-type") { answer.Type = 28; answer.Data = new byte[16]; }
            if (mode == "rdlength-long") answer.Data = new byte[] { 172, 16, 42, 1, 0 };
            if (mode == "rdlength-short") answer.Data = new byte[] { 172, 16, 42 };
            if (mode == "pointer-forward") answer.Owner = new byte[] { 192, (byte)(question.Length + 16) };
            if (mode == "pointer-outside") answer.Owner = new byte[] { 255, 255 };
            if (mode == "pointer-cycle") answer.Owner = new byte[] { 192, (byte)question.Length };
            if (mode != "no-answer") Record(result, answer); else result[7] = 0;
            if (mode == "identity") result[0] ^= 1;
            if (mode == "qr") result[2] &= 0x7f;
            if (mode == "opcode") result[2] |= 0x08;
            if (mode == "rcode") result[3] |= 3;
            if (mode == "truncated") result[2] |= 2;
            if (mode == "reserved-flag") result[3] |= 0x40;
            if (mode == "rd-bit") result[2] |= 1;
            if (mode == "question-count") result[5] = 2;
            if (mode == "question-name") result[13] = (byte)'j';
            if (mode == "question-type") result[question.Length - 3] = 28;
            if (mode == "question-class") result[question.Length - 1] = 3;
            if (mode == "label-too-large") result[12] = 64;
            if (mode == "label-character") result[13] = (byte)'.';
            if (mode == "trailing") result.Add(0);
            if (mode == "pointer-forward")
            {
                result[11] = 1;
                Record(result, new RecordSpec { Owner = Name("iphone-usb.home.arpa"), Type = 16, Data = new byte[] { 1, 120 } });
            }
            if (mode == "record-count")
            {
                result[7] = 65;
                for (int i = 1; i < 65; i++) Record(result, new RecordSpec());
            }
            if (mode == "largest" || mode == "oversized")
            {
                result[11] = 1;
                int padding = (mode == "largest" ? 4096 : 4097) - result.Count - 12;
                List<byte> text = new List<byte>();
                while (padding > 0)
                {
                    int length = Math.Min(255, padding - 1);
                    text.Add((byte)length);
                    for (int i = 0; i < length; i++) text.Add(120);
                    padding -= length + 1;
                }
                Record(result, new RecordSpec { Type = 16, Data = text.ToArray() });
            }
            if (mode == "extra")
            {
                result[9] = 1; result[11] = 10;
                Record(result, new RecordSpec { Type = 2, Data = Name("ns.home.arpa") });
                Record(result, new RecordSpec { Owner = Name("ns.home.arpa") });
                Record(result, new RecordSpec { Type = 5, Data = Name("alias.home.arpa") });
                Record(result, new RecordSpec { Type = 12, Data = Name("ptr.home.arpa") });
                List<byte> soa = new List<byte>(Name("ns.home.arpa"));
                soa.AddRange(Name("mail.home.arpa")); soa.AddRange(new byte[20]);
                Record(result, new RecordSpec { Type = 6, Data = soa.ToArray() });
                List<byte> mx = new List<byte>(new byte[] { 0, 10 }); mx.AddRange(Name("mx.home.arpa"));
                Record(result, new RecordSpec { Type = 15, Data = mx.ToArray() });
                List<byte> srv = new List<byte>(new byte[6]); srv.AddRange(Name("srv.home.arpa"));
                Record(result, new RecordSpec { Type = 33, Data = srv.ToArray() });
                Record(result, new RecordSpec { Type = 13, Data = new byte[] { 1, 120, 1, 121 } });
                Record(result, new RecordSpec { Type = 16, Data = new byte[] { 2, 120, 121 } });
                Record(result, new RecordSpec { Type = 28, Data = new byte[16] });
                Record(result, new RecordSpec { Owner = new byte[] { 0 }, Type = 41, Group = 4096, Ttl = 0, Data = new byte[] { 0, 10, 0, 1, 120 } });
            }
            if (mode.StartsWith("edns-", StringComparison.Ordinal))
            {
                RecordSpec opt = new RecordSpec { Owner = new byte[] { 0 }, Type = 41, Group = 4096, Ttl = 0, Data = new byte[0] };
                if (mode == "edns-rcode") opt.Ttl = 0x01000000;
                if (mode == "edns-version") opt.Ttl = 0x00010000;
                if (mode == "edns-flags") opt.Ttl = 1;
                if (mode == "edns-name") opt.Owner = new byte[] { 192, 12 };
                if (mode == "edns-option-overflow") opt.Data = new byte[] { 0, 1, 0, 2, 120 };
                if (mode == "edns-position") result[9] = 1; else result[11] = 1;
                Record(result, opt);
                if (mode == "edns-repeat") { result[11] = 2; Record(result, opt); }
            }
            if (mode == "txt-short" || mode == "soa-short" || mode == "unknown-type")
            {
                result[11] = 1;
                RecordSpec extra = new RecordSpec { Type = 16, Data = new byte[] { 2, 120 } };
                if (mode == "soa-short") { extra.Type = 6; extra.Data = new byte[] { 0, 0 }; }
                if (mode == "unknown-type") { extra.Type = 65200; extra.Data = new byte[] { 0 }; }
                Record(result, extra);
            }
            if (mode == "pointer-opaque")
            {
                result[11] = 2;
                byte[] encoded = Name("iphone-usb.home.arpa");
                List<byte> text = new List<byte>(new byte[] { (byte)encoded.Length }); text.AddRange(encoded);
                int target = result.Count + 13;
                Record(result, new RecordSpec { Type = 16, Data = text.ToArray() });
                Record(result, new RecordSpec { Owner = new byte[] { (byte)(0xc0 | (target >> 8)), (byte)target } });
            }
            if (mode == "upper-case") for (int i = 13; i < question.Length - 4; i++)
                if (result[i] >= 'a' && result[i] <= 'z') result[i] -= 32;
            if (mode == "short-message") return new byte[11];
            return result.ToArray();
        }
    }

    internal sealed class TestServer : IDisposable
    {
        internal readonly IPEndPoint Endpoint;
        internal volatile int Received;
        internal volatile Exception Error;
        private readonly UdpClient udp;
        private readonly TcpListener tcp;
        private readonly Thread thread;
        private readonly string mode;
        private volatile bool stopped;
        private volatile TcpClient active;

        internal TestServer(bool useTcp, string responseMode)
        {
            mode = responseMode;
            if (useTcp)
            {
                tcp = new TcpListener(IPAddress.Loopback, 0); tcp.Start();
                Endpoint = (IPEndPoint)tcp.LocalEndpoint;
            }
            else
            {
                udp = new UdpClient(new IPEndPoint(IPAddress.Loopback, 0));
                udp.Client.ReceiveTimeout = 250;
                Endpoint = (IPEndPoint)udp.Client.LocalEndPoint;
            }
            thread = new Thread(Serve); thread.IsBackground = true; thread.Start();
        }

        private static byte[] Exact(NetworkStream stream, int length)
        {
            byte[] data = new byte[length];
            int offset = 0;
            while (offset < length)
            {
                stream.ReadTimeout = 2000;
                int count = stream.Read(data, offset, length - offset);
                if (count == 0) throw new IOException("Fixture query incomplete.");
                offset += count;
            }
            return data;
        }

        private byte[] Reply(byte[] question)
        {
            if (question.Length != 38 || question[2] != 0 || question[3] != 0 ||
                question[4] != 0 || question[5] != 1 || question[6] != 0 || question[7] != 0 ||
                question[8] != 0 || question[9] != 0 || question[10] != 0 || question[11] != 0)
                throw new IOException("Fixture received malformed query.");
            Received++;
            return Packets.Reply(question, mode);
        }

        private void Serve()
        {
            DateTime end = DateTime.UtcNow.AddSeconds(10);
            try
            {
                if (udp != null)
                {
                    while (!stopped && DateTime.UtcNow < end)
                    {
                        try
                        {
                            IPEndPoint peer = new IPEndPoint(IPAddress.Any, 0);
                            byte[] reply = Reply(udp.Receive(ref peer));
                            if (mode != "silent") udp.Send(reply, reply.Length, peer);
                        }
                        catch (SocketException e) { if (e.SocketErrorCode != SocketError.TimedOut && !stopped) throw; }
                    }
                }
                else
                {
                    while (!stopped && DateTime.UtcNow < end)
                    {
                        if (!tcp.Pending()) { Thread.Sleep(10); continue; }
                        using (TcpClient client = tcp.AcceptTcpClient())
                        {
                            active = client;
                            using (NetworkStream stream = client.GetStream())
                            {
                                byte[] prefix = Exact(stream, 2);
                                int length = prefix[0] * 256 + prefix[1];
                                if (length != 38) throw new IOException("Fixture query length unexpected.");
                                byte[] reply = Reply(Exact(stream, length));
                                if (mode == "silent") { while (!stopped && DateTime.UtcNow < end) Thread.Sleep(20); }
                                else if (mode == "frame-too-large") stream.Write(new byte[] { 16, 1 }, 0, 2);
                                else if (mode == "frame-too-short") stream.Write(new byte[] { 0, 11 }, 0, 2);
                                else if (mode == "frame-eof") stream.Write(new byte[] { 0, 54, 0 }, 0, 3);
                                else
                                {
                                    byte[] frame = new byte[reply.Length + 2];
                                    frame[0] = (byte)(reply.Length >> 8); frame[1] = (byte)reply.Length;
                                    Array.Copy(reply, 0, frame, 2, reply.Length);
                                    if (mode == "fragmented")
                                    {
                                        for (int i = 0; i < frame.Length; i++) { stream.Write(frame, i, 1); Thread.Sleep(2); }
                                    }
                                    else if (mode == "drip")
                                    {
                                        stream.Write(frame, 0, 2);
                                        for (int i = 2; i < 7 && !stopped; i++)
                                        {
                                            stream.Write(frame, i, 1); Thread.Sleep(1200);
                                        }
                                    }
                                    else stream.Write(frame, 0, frame.Length);
                                }
                            }
                            active = null;
                        }
                    }
                }
            }
            catch (Exception error) { if (!stopped) Error = error; }
        }

        public void Dispose()
        {
            stopped = true;
            if (active != null) active.Close();
            if (udp != null) udp.Close();
            if (tcp != null) tcp.Stop();
            if (!thread.Join(5000)) throw new IOException("Fixture thread did not terminate.");
        }
    }

    public static class DnsHarness
    {
        private static Query Query()
        {
            return Client.MakeQuery("iphone-usb.home.arpa", IPAddress.Parse("172.16.42.1"));
        }

        private static void Assert(bool condition, string message)
        {
            if (!condition) throw new DnsAssertionException(message);
        }

        private static void Refuse(Action action, string name)
        {
            try { action(); }
            catch (InvalidDataException) { return; }
            throw new DnsAssertionException(name + ": malformed response accepted.");
        }

        private static void PrivateAddresses()
        {
            foreach (string address in new string[] { "8.8.8.8", "127.0.0.1", "0.0.0.0", "::1", "172.15.0.1", "172.32.0.1", "10.1", "0x0a000001" })
            {
                bool refused = false;
                try { Client.PrivateAddress(address); } catch (ArgumentException) { refused = true; }
                Assert(refused, "Forbidden target accepted: " + address);
            }
            foreach (string address in new string[] { "10.0.0.1", "172.16.0.1", "172.31.255.254", "192.168.1.1" })
                Assert(Client.PrivateAddress(address).ToString() == address, "Private target normalization failed.");
            foreach (string name in new string[] { "example.com", "home.arpa", "a..home.arpa", "-a.home.arpa", new string('a', 64) + ".home.arpa" })
            {
                bool refused = false;
                try { Client.MakeQuery(name, IPAddress.Parse("172.16.42.1")); } catch (ArgumentException) { refused = true; }
                Assert(refused, "Forbidden DNS name accepted.");
            }
        }

        private static void Transport(string name)
        {
            bool tcp = !name.StartsWith("udp-", StringComparison.Ordinal);
            string mode = name.Substring(4);
            if (mode == "wrong-port")
            {
                using (TestServer intended = new TestServer(tcp, "good"))
                using (TestServer wrong = new TestServer(tcp, "silent"))
                {
                    bool failed = false;
                    try { Client.Exchange(wrong.Endpoint, Query().Message, tcp); }
                    catch (IOException) { failed = true; }
                    catch (SocketException) { failed = true; }
                    Assert(failed && intended.Received == 0 && wrong.Received == 1,
                           "Wrong port did not produce a real isolated failure.");
                    Assert(intended.Error == null && wrong.Error == null, "Wrong-port fixture failed.");
                }
                return;
            }
            using (TestServer server = new TestServer(tcp, mode))
            {
                Query query = Query();
                Stopwatch clock = Stopwatch.StartNew();
                bool refused = false;
                try
                {
                    byte[] reply = Client.Exchange(server.Endpoint, query.Message, tcp);
                    Client.Validate(reply, query);
                }
                catch (InvalidDataException) { refused = true; }
                catch (IOException) { refused = true; }
                catch (SocketException) { refused = true; }
                bool positive = mode == "good" || mode == "literal" || mode == "fragmented" || mode == "extra";
                Assert(refused != positive, name + ": transport outcome incorrect.");
                Assert(server.Error == null, name + ": fixture failed: " + server.Error);
                Assert(server.Received == 1, name + ": actual query not received.");
                if (mode == "silent" || mode == "drip") Assert(clock.ElapsedMilliseconds < 4200, name + ": deadline not bounded.");
            }
        }

        public static void RunOne(string name)
        {
            if (name == "private-address") { PrivateAddresses(); return; }
            if (name == "query-id")
            {
                Query first = Query();
                bool varied = false;
                for (int i = 0; i < 8; i++)
                {
                    Query next = Query();
                    varied |= first.Message[0] != next.Message[0] || first.Message[1] != next.Message[1];
                }
                Assert(varied, "Transaction IDs are constant.");
                return;
            }
            if (name.StartsWith("udp-", StringComparison.Ordinal) || name.StartsWith("tcp-", StringComparison.Ordinal))
            { Transport(name); return; }
            Query query = Query();
            byte[] packet = Packets.Reply(query.Message, name);
            if (name == "good" || name == "literal" || name == "extra" || name == "largest" || name == "upper-case")
                Client.Validate(packet, query);
            else Refuse(() => Client.Validate(packet, query), name);
        }

        public static string[] Cases()
        {
            return new string[] {
                "good", "literal", "extra", "largest", "upper-case", "private-address", "query-id",
                "identity", "qr", "opcode", "rcode", "truncated", "reserved-flag", "rd-bit",
                "question-count", "record-count", "question-name", "question-type", "question-class",
                "owner", "address", "record-class", "answer-type", "no-answer", "rdlength-long", "rdlength-short",
                "trailing", "label-too-large", "label-character", "pointer-forward", "pointer-outside",
                "pointer-cycle", "pointer-opaque", "oversized", "short-message", "edns-rcode", "edns-version",
                "edns-flags", "edns-name", "edns-position", "edns-repeat", "edns-option-overflow",
                "txt-short", "soa-short", "unknown-type", "udp-good", "tcp-good", "udp-literal", "tcp-fragmented",
                "udp-extra", "tcp-extra", "udp-identity", "tcp-address", "udp-truncated", "tcp-frame-too-large",
                "tcp-frame-too-short", "tcp-frame-eof", "udp-silent", "tcp-silent", "tcp-drip", "udp-wrong-port"
            };
        }
    }
}

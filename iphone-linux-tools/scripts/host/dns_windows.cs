using System;
using System.Collections.Generic;
using System.Diagnostics;
using System.IO;
using System.Net;
using System.Net.Sockets;
using System.Security.Cryptography;
using System.Text;
using System.Text.RegularExpressions;

namespace IphoneDns
{
    public sealed class QueryOptions
    {
        public string ServerAddress { get; set; }
        public string ExpectedAddress { get; set; }
        public string Name { get; set; }
        public int Port { get; set; }
    }

    internal sealed class Query
    {
        internal byte[] Message;
        internal string Name;
        internal IPAddress Expected;
    }

    internal sealed class Reader
    {
        internal readonly byte[] Data;
        internal int Offset;
        private readonly HashSet<int> labels = new HashSet<int>();

        internal Reader(byte[] data) { Data = data; }

        internal void Require(int length)
        {
            if (length < 0 || Offset > Data.Length - length)
                throw new InvalidDataException("DNS field exceeds message.");
        }

        internal int U16()
        {
            Require(2);
            int value = Data[Offset] * 256 + Data[Offset + 1];
            Offset += 2;
            return value;
        }

        internal uint U32()
        {
            Require(4);
            uint value = ((uint)Data[Offset] << 24) | ((uint)Data[Offset + 1] << 16) |
                         ((uint)Data[Offset + 2] << 8) | Data[Offset + 3];
            Offset += 4;
            return value;
        }

        internal string Name(int limit)
        {
            int cursor = Offset, consumed = -1, wireLength = 1;
            List<string> parts = new List<string>();
            HashSet<int> visited = new HashSet<int>();
            for (int step = 0; step < 128; step++)
            {
                if (cursor >= limit || !visited.Add(cursor))
                    throw new InvalidDataException("DNS name is truncated or cyclic.");
                int start = cursor;
                int size = Data[cursor++];
                labels.Add(start);
                if ((size & 0xc0) == 0xc0)
                {
                    if (cursor >= limit) throw new InvalidDataException("DNS pointer truncated.");
                    int target = ((size & 0x3f) << 8) | Data[cursor++];
                    if (target < 12 || target >= start || !labels.Contains(target))
                        throw new InvalidDataException("DNS pointer target refused.");
                    if (consumed < 0) consumed = cursor;
                    cursor = target;
                    limit = Data.Length;
                    continue;
                }
                if (size > 63 || cursor > limit - size)
                    throw new InvalidDataException("DNS label invalid.");
                if (size == 0)
                {
                    Offset = consumed < 0 ? cursor : consumed;
                    return String.Join(".", parts.ToArray()).ToLowerInvariant();
                }
                wireLength += size + 1;
                if (wireLength > 255) throw new InvalidDataException("DNS name too long.");
                for (int i = cursor; i < cursor + size; i++)
                {
                    byte b = Data[i];
                    if (!(b >= 'a' && b <= 'z' || b >= 'A' && b <= 'Z' ||
                          b >= '0' && b <= '9' || b == '-' || b == '_'))
                        throw new InvalidDataException("DNS label character unsupported.");
                }
                parts.Add(Encoding.ASCII.GetString(Data, cursor, size));
                cursor += size;
            }
            throw new InvalidDataException("DNS compression hop limit exceeded.");
        }

        internal void Text(int end)
        {
            if (Offset >= end) throw new InvalidDataException("DNS text missing.");
            int length = Data[Offset++];
            if (Offset > end - length) throw new InvalidDataException("DNS text truncated.");
            Offset += length;
        }
    }

    internal sealed class ParseContext
    {
        internal Reader Reader;
        internal Query Query;
        internal int Matches;
        internal bool Opt;
    }

    public static class Client
    {
        internal const int MaximumMessage = 4096;
        internal const int DeadlineMilliseconds = 3000;

        public static IPAddress PrivateAddress(string value)
        {
            IPAddress address;
            if (!IPAddress.TryParse(value, out address) ||
                address.AddressFamily != AddressFamily.InterNetwork || address.ToString() != value)
                throw new ArgumentException("An explicit canonical private IPv4 is required.");
            byte[] b = address.GetAddressBytes();
            if (!(b[0] == 10 || b[0] == 172 && b[1] >= 16 && b[1] <= 31 ||
                  b[0] == 192 && b[1] == 168))
                throw new ArgumentException("Public, wildcard and loopback addresses are refused.");
            return address;
        }

        internal static Query MakeQuery(string name, IPAddress expected)
        {
            if (name == null) throw new ArgumentException("DNS name missing.");
            name = name.ToLowerInvariant().TrimEnd('.');
            if (name.Length > 253 || !name.EndsWith(".home.arpa", StringComparison.Ordinal))
                throw new ArgumentException("Only valid home.arpa names are accepted.");
            List<byte> data = new List<byte>(new byte[12]);
            byte[] id = new byte[2];
            using (RandomNumberGenerator random = RandomNumberGenerator.Create()) random.GetBytes(id);
            data[0] = id[0]; data[1] = id[1]; data[5] = 1;
            foreach (string label in name.Split('.'))
            {
                if (!Regex.IsMatch(label, "^[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?$"))
                    throw new ArgumentException("DNS label invalid.");
                data.Add((byte)label.Length);
                data.AddRange(Encoding.ASCII.GetBytes(label));
            }
            data.AddRange(new byte[] { 0, 0, 1, 0, 1 });
            return new Query { Message = data.ToArray(), Name = name, Expected = expected };
        }

        public static void Check(QueryOptions options, bool tcp)
        {
            if (options == null || (options.Port != 53 && options.Port < 1024) || options.Port > 65535)
                throw new ArgumentException("DNS port must be 53 or between 1024 and 65535.");
            IPEndPoint endpoint = new IPEndPoint(PrivateAddress(options.ServerAddress), options.Port);
            Query query = MakeQuery(options.Name, PrivateAddress(options.ExpectedAddress));
            Validate(Exchange(endpoint, query.Message, tcp), query);
        }

        private static int Remaining(Stopwatch clock)
        {
            int remaining = DeadlineMilliseconds - (int)clock.ElapsedMilliseconds;
            if (remaining <= 0) throw new IOException("DNS query deadline exceeded.");
            return remaining;
        }

        private static byte[] Exact(NetworkStream stream, int length, Stopwatch clock)
        {
            byte[] data = new byte[length];
            int offset = 0;
            while (offset < length)
            {
                stream.ReadTimeout = Remaining(clock);
                int count = stream.Read(data, offset, length - offset);
                if (count == 0) throw new IOException("Incomplete DNS TCP frame.");
                offset += count;
            }
            Remaining(clock);
            return data;
        }

        internal static byte[] Exchange(IPEndPoint endpoint, byte[] message, bool tcp)
        {
            Stopwatch clock = Stopwatch.StartNew();
            if (!tcp)
            {
                using (Socket socket = new Socket(AddressFamily.InterNetwork, SocketType.Dgram, ProtocolType.Udp))
                {
                    socket.Connect(endpoint);
                    socket.SendTimeout = Remaining(clock);
                    if (socket.Send(message) != message.Length) throw new IOException("DNS send incomplete.");
                    socket.ReceiveTimeout = Remaining(clock);
                    byte[] buffer = new byte[MaximumMessage + 1];
                    int length = socket.Receive(buffer);
                    Remaining(clock);
                    if (length < 12 || length > MaximumMessage)
                        throw new InvalidDataException("DNS datagram size refused.");
                    byte[] reply = new byte[length];
                    Array.Copy(buffer, reply, length);
                    return reply;
                }
            }
            using (TcpClient client = new TcpClient(AddressFamily.InterNetwork))
            {
                IAsyncResult connection = client.BeginConnect(endpoint.Address, endpoint.Port, null, null);
                using (System.Threading.WaitHandle ready = connection.AsyncWaitHandle)
                {
                    if (!ready.WaitOne(Remaining(clock))) throw new IOException("DNS connect deadline exceeded.");
                    client.EndConnect(connection);
                }
                using (NetworkStream stream = client.GetStream())
                {
                    byte[] frame = new byte[message.Length + 2];
                    frame[0] = (byte)(message.Length >> 8); frame[1] = (byte)message.Length;
                    Array.Copy(message, 0, frame, 2, message.Length);
                    stream.WriteTimeout = Remaining(clock);
                    stream.Write(frame, 0, frame.Length);
                    byte[] prefix = Exact(stream, 2, clock);
                    int length = prefix[0] * 256 + prefix[1];
                    if (length < 12 || length > MaximumMessage)
                        throw new InvalidDataException("DNS frame size refused.");
                    return Exact(stream, length, clock);
                }
            }
        }

        internal static void Validate(byte[] message, Query query)
        {
            if (message.Length < 12 || message.Length > MaximumMessage)
                throw new InvalidDataException("DNS message size refused.");
            Reader reader = new Reader(message);
            int id = reader.U16();
            if (id != query.Message[0] * 256 + query.Message[1])
                throw new InvalidDataException("DNS transaction identity mismatch.");
            int flags = reader.U16();
            if ((flags & 0x8000) == 0 || (flags & 0x7a4f) != 0 || (flags & 0x0100) != 0)
                throw new InvalidDataException("DNS flags, truncation or status refused.");
            int questions = reader.U16(), answers = reader.U16(), authority = reader.U16(), additional = reader.U16();
            if (questions != 1 || answers + authority + additional > 64)
                throw new InvalidDataException("DNS section counts refused.");
            if (reader.Name(message.Length) != query.Name || reader.U16() != 1 || reader.U16() != 1)
                throw new InvalidDataException("DNS question mismatch.");
            ParseContext context = new ParseContext { Reader = reader, Query = query };
            Records(context, answers, 0);
            Records(context, authority, 1);
            Records(context, additional, 2);
            if (context.Matches == 0 || reader.Offset != message.Length)
                throw new InvalidDataException("DNS answer missing or trailing bytes present.");
        }

        private static void Records(ParseContext context, int count, int section)
        {
            Reader reader = context.Reader;
            for (int record = 0; record < count; record++)
            {
                string name = reader.Name(reader.Data.Length);
                int type = reader.U16(), group = reader.U16();
                uint ttl = reader.U32();
                int length = reader.U16();
                reader.Require(length);
                int end = reader.Offset + length;
                if (type != 41 && group != 1) throw new InvalidDataException("DNS record class refused.");
                switch (type)
                {
                    case 1:
                        if (length != 4) throw new InvalidDataException("DNS A size refused.");
                        byte[] address = new byte[4];
                        Array.Copy(reader.Data, reader.Offset, address, 0, 4);
                        reader.Offset = end;
                        if (section == 0)
                        {
                            if (name != context.Query.Name) throw new InvalidDataException("DNS answer owner mismatch.");
                            if (!new IPAddress(address).Equals(context.Query.Expected))
                                throw new InvalidDataException("DNS answer address mismatch.");
                            context.Matches++;
                        }
                        break;
                    case 28:
                        if (length != 16) throw new InvalidDataException("DNS AAAA size refused.");
                        reader.Offset = end;
                        break;
                    case 2: case 5: case 12:
                        reader.Name(end);
                        break;
                    case 6:
                        reader.Name(end); reader.Name(end);
                        if (end - reader.Offset != 20) throw new InvalidDataException("DNS SOA size refused.");
                        reader.Offset = end;
                        break;
                    case 15:
                        if (length < 3) throw new InvalidDataException("DNS MX size refused.");
                        reader.U16(); reader.Name(end);
                        break;
                    case 33:
                        if (length < 7) throw new InvalidDataException("DNS SRV size refused.");
                        reader.U16(); reader.U16(); reader.U16(); reader.Name(end);
                        break;
                    case 13:
                        reader.Text(end); reader.Text(end);
                        break;
                    case 16:
                        if (length == 0) throw new InvalidDataException("DNS TXT empty.");
                        while (reader.Offset < end) reader.Text(end);
                        break;
                    case 41:
                        if (section != 2 || name != "" || context.Opt || (ttl >> 16) != 0 || (ttl & 0x7fff) != 0)
                            throw new InvalidDataException("DNS EDNS header refused.");
                        context.Opt = true;
                        while (reader.Offset < end)
                        {
                            if (end - reader.Offset < 4) throw new InvalidDataException("DNS EDNS option truncated.");
                            reader.U16();
                            int optionLength = reader.U16();
                            if (reader.Offset > end - optionLength) throw new InvalidDataException("DNS EDNS option exceeds record.");
                            reader.Offset += optionLength;
                        }
                        break;
                    default:
                        throw new InvalidDataException("Unsupported DNS resource record type.");
                }
                if (reader.Offset != end || section == 0 && type != 1)
                    throw new InvalidDataException("DNS RDATA size or answer type refused.");
            }
        }
    }
}

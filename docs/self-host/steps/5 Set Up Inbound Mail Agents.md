## Step 5: Set Up Inbound Mail Agents

Inbound Mail Agents handle the receiving of emails. Their setup is similar to outbound agents, but you don’t need to worry about checking the IP blacklist status for inbound agents since they aren't responsible for sending emails.

### 5.1 Add a DNS A Record

Create a DNS record for your inbound Mail Agent using the following naming convention:

```plaintext
<agent-type><agent-number>-<region-short-name>.<root-domain>
```

For example, for the first inbound Mail Agent in Bangalore:

```plaintext
i1-blr.frappemail.com
```

**Steps to Add the DNS Record:**

1. **Login to your DNS provider's dashboard** (such as Cloudflare, GoDaddy, etc.).
2. **Add an A Record:**

   - **Name:** `i1-blr` (or your chosen name based on the convention)
   - **Type:** A
   - **TTL:** Auto or a specific TTL value
   - **Value:** IP address of your inbound Mail Agent VPS

   This will make the inbound Mail Agent accessible via the defined hostname.

### 5.2 Install Inbound Mail Agent

Once the DNS record is created, proceed with the installation. The steps are similar to Step 4 for outbound agents, with one key difference. Instead of the regular outbound setup command, use the following to configure the inbound agent:

```bash
mail-agent setup --inbound --prod
```

This enables the agent to handle inbound emails.

### 5.3 Set Up Additional Inbound Mail Agents

If you need more inbound Mail Agents, repeat the DNS and installation steps. For example, for a second inbound Mail Agent in Bangalore, create the following DNS record:

```plaintext
i2-blr.frappemail.com
```

Follow the same process to install and configure the additional agents.

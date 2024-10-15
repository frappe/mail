# Setting up Frappe Mail for Production (Self-Hosted)

> _**Note**: Frappe Mail is not yet fully production-ready. Therefore, it is advised not to rely on it entirely for critical email services at this stage._

This guide details the exact process we followed to set up and run `frappemail.com` as a mail service. Setting up Frappe Mail involves multiple components and services, and while the process is straightforward, it does require attention to detail at each step.

By following this documentation, you’ll learn how to replicate the setup used for `frappemail.com`, ensuring your mail service is fully operational and optimized for production use.

## Who Should Self-Host Frappe Mail?

Self-hosting **Frappe Mail** is best suited for businesses or individuals with high email volume (e.g., sending around **100,000 emails per day**) or for those looking to start their own email service. If your email volume is substantial, hosting your own Frappe Mail server provides better control and scalability.

For those with **low email volumes**, setting up and maintaining Frappe Mail may be more **expensive** compared to using a third-party email service or **Frappe Mail as a Service** (coming soon on **Frappe Cloud**), which will offer a more affordable solution for smaller operations.

## Prerequisites

Before we dive into the setup, ensure you have the following in place:

1. **A Domain Name with DNS Access:** Ensure that you have control over a domain name that is at least 1–3 months old. Using an established domain helps improve email delivery reputation and reduces the risk of blacklisting. In this guide, we will be using `frappemail.com` as the root domain.
2. **1 VPS for RabbitMQ:** RabbitMQ will serve as the message broker to handle the email queue between your services. It's recommended to have a dedicated VPS for RabbitMQ.
3. **1 VPS for SpamAssassin:** SpamAssassin will handle spam filtering for both inbound and outbound emails. A separate VPS ensures that spam filtering does not interfere with other processes.
4. **2 VPS for Outbound Mail Agents:** These servers will act as outbound mail transfer agents (MTAs), handling all outbound email traffic for your domain(s). Using two servers ensures better load management and redundancy.
5. **2 VPS for Inbound Mail Agents:** Inbound mail agents will handle and process incoming emails. Having two servers ensures smooth reception and scalability for your incoming mail.
6. **Frappe Bench:** A Frappe Bench where the Mail app will be installed. You’ll use this environment to manage and configure your **domains**, **mailboxes**, and other email-related settings.

### Minimal Setup Recommendation:

While the above setup is ideal, it’s not mandatory to start with 6 VPS. You can begin with just **2 VPS**:

- One VPS for **Inbound Mail**, and
- One VPS for **Outbound Mail**, while **RabbitMQ** and **SpamAssassin** can also be installed on this second server.

For the 2-VPS setup:

- **Inbound VPS**: 1GB RAM, 1 vCPU (for handling incoming mail).
- **Outbound VPS**: 2GB RAM, 2 vCPUs (for outbound email, RabbitMQ, and SpamAssassin).

This minimal setup allows you to start with lower resources and scale up later as your email traffic grows.

If you are using the **4-VPS approach** (dedicated VPS for RabbitMQ, SpamAssassin, Outbound Mail Agent, and Inbound Mail Agent) or the **6-VPS approach** (RabbitMQ, SpamAssassin, 2 Outbound Mail Agents, 2 Inbound Mail Agents), you can allocate **1GB RAM and 1 vCPU** for each VPS. This setup ensures optimal resource allocation for each service while maintaining scalability.

> **Tip:** We recommend using Ubuntu 24.04, as it’s thoroughly tested with Frappe Mail. If you are using different configurations, adjust accordingly based on your resource needs.

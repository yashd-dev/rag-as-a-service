import { betterAuth } from "better-auth";
import { drizzleAdapter } from "better-auth/adapters/drizzle";
import { nextCookies } from "better-auth/next-js";
import { createAccessControl } from "better-auth/plugins/access";
import { defaultStatements } from "better-auth/plugins/organization/access";
import { magicLink, organization } from "better-auth/plugins";
import { Resend } from "resend";

import { db } from "@/db";
import * as schema from "@/lib/auth-schema";

const resend = new Resend(process.env.RESEND_API_KEY);
const ac = createAccessControl(defaultStatements);
const manager = ac.newRole({
  organization: [],
  invitation: ["create", "cancel"],
  member: ["delete"],
  team: [],
  ac: ["read"],
});
const inviter = ac.newRole({
  organization: [],
  invitation: ["create"],
  member: [],
  team: [],
  ac: ["read"],
});
const member = ac.newRole({
  organization: [],
  invitation: [],
  member: [],
  team: [],
  ac: ["read"],
});

function escapeHtml(value: string) {
  return value.replaceAll("&", "&amp;").replaceAll('"', "&quot;");
}

function magicLinkEmail(url: string) {
  const safeUrl = escapeHtml(url);

  return `
    <div style="margin:0;background:#f6f6f6;padding:32px 16px;font-family:Arial,sans-serif;color:#111111;">
      <div style="margin:0 auto;max-width:520px;border:1px solid #e5e5e5;border-radius:16px;background:#ffffff;padding:32px;">
        <p style="margin:0 0 16px;font-size:13px;color:#737373;">Recall</p>
        <h1 style="margin:0;font-size:24px;font-weight:600;line-height:1.3;color:#111111;">Sign in to Recall</h1>
        <p style="margin:16px 0 24px;font-size:15px;line-height:1.6;color:#525252;">Use the link below to sign in. It expires soon.</p>
        <a href="${safeUrl}" style="display:inline-block;border-radius:10px;background:#111111;padding:12px 18px;font-size:14px;font-weight:600;color:#ffffff;text-decoration:none;">Sign in</a>
        <p style="margin:24px 0 0;font-size:12px;line-height:1.6;color:#737373;">If you did not request this email, you can ignore it.</p>
      </div>
    </div>`;
}

function inviteEmail(input: { url: string; organization: string; inviter: string; role: string }) {
  const safeUrl = escapeHtml(input.url);

  return `
    <div style="margin:0;background:#f6f6f6;padding:32px 16px;font-family:Arial,sans-serif;color:#111111;">
      <div style="margin:0 auto;max-width:520px;border:1px solid #e5e5e5;border-radius:16px;background:#ffffff;padding:32px;">
        <p style="margin:0 0 16px;font-size:13px;color:#737373;">Recall</p>
        <h1 style="margin:0;font-size:24px;font-weight:600;line-height:1.3;color:#111111;">Join ${escapeHtml(input.organization)}</h1>
        <p style="margin:16px 0 24px;font-size:15px;line-height:1.6;color:#525252;">${escapeHtml(input.inviter)} invited you as ${escapeHtml(input.role)}.</p>
        <a href="${safeUrl}" style="display:inline-block;border-radius:10px;background:#111111;padding:12px 18px;font-size:14px;font-weight:600;color:#ffffff;text-decoration:none;">Accept invite</a>
        <p style="margin:24px 0 0;font-size:12px;line-height:1.6;color:#737373;">Use the invited email address to join this workspace.</p>
      </div>
    </div>`;
}

export const auth = betterAuth({
  database: drizzleAdapter(db, { provider: "sqlite", schema }),
  baseURL: process.env.BETTER_AUTH_URL,
  secret: process.env.BETTER_AUTH_SECRET,
  plugins: [
    magicLink({
      async sendMagicLink({ email, url }) {
        const from = "rag@yashd.in";

        if (!process.env.RESEND_API_KEY) {
          throw new Error("RESEND_API_KEY is required to send magic links");
        }

        if (!from) {
          throw new Error("RESEND_FROM_EMAIL is required to send magic links");
        }

        const { error } = await resend.emails.send({
          from,
          to: email,
          subject: "Sign in to Recall",
          html: magicLinkEmail(url),
          text: `Sign in to Recall: ${url}`,
          tags: [{ name: "category", value: "magic-link" }],
        });

        if (error) {
          throw new Error(error.message);
        }
      },
    }),
    organization({
      ac,
      roles: { manager, inviter, member },
      async sendInvitationEmail(data) {
        const from = "rag@yashd.in";
        const inviteUrl = new URL(`/invite/${data.id}`, process.env.BETTER_AUTH_URL).toString();

        if (!process.env.RESEND_API_KEY) {
          throw new Error("RESEND_API_KEY is required to send invitations");
        }

        const { error } = await resend.emails.send({
          from,
          to: data.email,
          subject: `Join ${data.organization.name} on Recall`,
          html: inviteEmail({
            url: inviteUrl,
            organization: data.organization.name,
            inviter: data.inviter.user.name || data.inviter.user.email,
            role: data.role,
          }),
          text: `${data.inviter.user.name || data.inviter.user.email} invited you to ${data.organization.name} on Recall: ${inviteUrl}`,
          tags: [{ name: "category", value: "organization-invite" }],
        });

        if (error) {
          throw new Error(error.message);
        }
      },
    }),
    nextCookies(),
  ],
});

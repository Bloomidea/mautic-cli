"""Command groups for mautic-cli."""


def register_commands(cli):
    """Register all command groups with the CLI."""
    from mautic_cli.commands.contacts import contacts
    from mautic_cli.commands.segments import segments
    from mautic_cli.commands.emails import emails
    from mautic_cli.commands.campaigns import campaigns
    from mautic_cli.commands.auth_cmd import auth
    from mautic_cli.commands.forms import forms
    from mautic_cli.commands.companies import companies
    from mautic_cli.commands.notes import notes
    from mautic_cli.commands.stages import stages
    from mautic_cli.commands.assets import assets
    from mautic_cli.commands.tags import tags
    from mautic_cli.commands.categories import categories
    from mautic_cli.commands.pages import pages
    from mautic_cli.commands.webhooks import webhooks
    from mautic_cli.commands.fields import fields
    from mautic_cli.commands.reports import reports
    from mautic_cli.commands.points import points
    from mautic_cli.commands.focus import focus
    from mautic_cli.commands.stats import stats

    cli.add_command(contacts)
    cli.add_command(segments)
    cli.add_command(emails)
    cli.add_command(campaigns)
    cli.add_command(auth)
    cli.add_command(forms)
    cli.add_command(companies)
    cli.add_command(notes)
    cli.add_command(stages)
    cli.add_command(assets)
    cli.add_command(tags)
    cli.add_command(categories)
    cli.add_command(pages)
    cli.add_command(webhooks)
    cli.add_command(fields)
    cli.add_command(reports)
    cli.add_command(points)
    cli.add_command(focus)
    cli.add_command(stats)

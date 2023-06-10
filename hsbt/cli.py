import click


@click.command()
@click.option("--count", default=1, help="Number of greetings.")
@click.option("--name", prompt="Your name", help="The person to greet.")
def main(count, name):
    """Simple program that greets NAME for a total of COUNT times."""
    for _ in range(count):
        click.echo(f"Hello, {name}!")


def create_connection(connection_identifier: str):
    # save connection params as json in /etc/hetzner_connections.json when root or ~/.config/hetzner_connections.json if non root
    # exchange key with hetzner storage box.
    pass


def list_connections():
    pass


def run_remote_command(connection_identifier: str):
    # allowd commands https://docs.hetzner.com/de/robot/storage-box/access/access-ssh-rsync-borg#verfugbare-befehle
    # if identifier is passed check for matching connection params in /etc/hetzner_connections.json or ~/.config/hetzner_connections.json
    # othwerwise params must be passed as function params
    pass


def mount(connection_identifier: str):
    pass


def available_space(connection_identifier: str):
    pass


def download_from_remote(connection_identifier: str):
    pass


def upload_to_remote(connection_identifier: str):
    pass


if __name__ == "__main__":
    main()
